# Hybrid Search Pipeline — Spec Design

## Purpose

Retrieves the top-K past incidents most similar to a new analyst report. Combines semantic (dense vector) search with keyword (BM25) search, fused via Reciprocal Rank Fusion (RRF). Results are passed to Call 3 (mitigation) as grounding context.

---

## Architecture Overview

```
data/raw.json  ──►  search/index.py  ──►  search/chroma_db/    (dense vectors, uuid in metadata)
                                     └──►  search/bm25s_index/  (BM25 index + corpus [{uuid}])

retrieve(query, k=2)
  ├── ChromaDB semantic search  → top-N uuids
  ├── BM25 keyword search       → top-N uuids
  ├── RRF fusion (k=60)         → ranked uuids
  ├── Load data/raw.json[uuid]  → {summary, mitigation}
  └── return [{uuid, summary, mitigation}]
```

---

## Data

### `data/raw.json` — source of truth

Single JSON file, keyed by uuid:

```json
{
  "uuid-1": {
    "summary": "3–5 sentence narrative of the past incident...",
    "mitigation": "What was done to respond and remediate..."
  }
}
```

**Rules:**
- `summary` is the only text indexed — by both ChromaDB and BM25
- `mitigation` lives only here — not duplicated into any index
- New entries are appended by the pipeline after Call 3 completes
- uuid keys are generated with `uuid.uuid4()`

---

## Indexing (`search/index.py`)

Run once manually to build or rebuild all indices from `data/raw.json`. Always a full rebuild — ChromaDB handles duplicate ids via upsert; BM25 is not an online algorithm and must be rebuilt from scratch.

### `load_raw(path: str) -> dict`
Loads and returns `data/raw.json` as a dict keyed by uuid.

### `build_chroma_index(ids: list[str], summaries: list[str], chroma_path: str)`
Creates or updates a ChromaDB `PersistentClient` collection at `chroma_path`. Upserts all incidents with `summary` as the document and `uuid` as metadata. Uses ChromaDB's default embedding function (`all-MiniLM-L6-v2`).

### `build_bm25_index(ids: list[str], summaries: list[str], bm25_path: str)`
Tokenizes summaries, builds a `bm25s.BM25` index, and persists it to `bm25_path` via `retriever.save(corpus=[{"uuid": uid} for uid in ids])`. Corpus stores only uuids — no data duplication.

### `build_index()`
Entry point. Calls `load_raw`, then `build_chroma_index` and `build_bm25_index`. Run as `__main__`.

---

## Retrieval (`search/retriever.py`)

Exposes one public function. Indices are loaded on each call — no module-level singletons.

### `_load_chroma(chroma_path: str) -> chromadb.Collection`
Loads the persisted ChromaDB collection from `chroma_path`. Returns the collection object.

### `_load_bm25(bm25_path: str) -> bm25s.BM25`
Loads the persisted BM25 index from `bm25_path` using `mmap=True`.

### `_semantic_search(collection, query: str, n: int) -> list[str]`
Queries ChromaDB for the top-N most semantically similar incidents. Returns a list of uuids in ranked order.

### `_bm25_search(retriever, query: str, n: int) -> list[str]`
Tokenizes the query and retrieves the top-N BM25 matches. Maps result positions back to uuids via `retriever.corpus`. Returns a list of uuids in ranked order.

### `_rrf(rankings: list[list[str]], k: int = 60) -> list[str]`
Applies Reciprocal Rank Fusion across multiple ranked uuid lists. Score per document: `Σ 1 / (k + rank_i)` summed over all lists. Documents appearing in only one list receive a partial score. Returns all uuids sorted by descending RRF score. `k=60` is a fixed constant — not the number of results to return.

### `_load_incidents(uuids: list[str], raw_path: str) -> list[dict]`
Loads `data/raw.json` and returns the full records `{uuid, summary, mitigation}` for the given uuids, preserving order.

### `retrieve(query: str, k: int = 2) -> list[dict]`
Public entry point. Loads both indices, runs semantic and BM25 search (each returning `CANDIDATE_N=10` results), fuses with RRF, takes the top-k uuids, loads their records from `raw.json`, and returns `[{uuid, summary, mitigation}]`.

---

## Output

`retrieve()` returns a list of dicts:

```python
[
  {
    "uuid": "abc-123",
    "summary": "Past incident summary narrative...",
    "mitigation": "What was done to respond..."
  }
]
```

Passed directly into the mitigation prompt builder (Call 3) as context.

---

## Write-back (`search/writer.py`)

Called by the pipeline after Call 3 completes to persist the new incident.

### `save_incident(summary: str, mitigation: str, raw_path: str) -> str`
Generates a new uuid, appends `{summary, mitigation}` to `data/raw.json` under that uuid, writes the file back, and returns the uuid. Re-running `index.py` picks up the new entry in the next session.

---

## Dummy Data

15 pre-populated incidents in `data/raw.json` covering:
- OTA supply chain attacks
- TCU/RCE remote exploitation
- CAN bus injection
- Key relay / PKES theft
- Telematics data exfiltration
- Infotainment pivot attacks
- TPMS spoofing
- V2X protocol abuse

---

## Production Upgrade Path

| Component | PoC | Production |
|---|---|---|
| Vector DB | ChromaDB local (`PersistentClient`) | Weaviate / Qdrant / ChromaDB Cloud |
| BM25 | bm25s local file | Built into Weaviate/Qdrant natively |
| Hybrid fusion | Manual RRF | Native hybrid query in DB |
| Incremental indexing | Full rebuild | DB upsert per new document |
| Raw storage | `data/raw.json` | S3 — one object per incident |
| ETL trigger | Manual `index.py` run | S3 event → Lambda → DB upsert |

---

## Files Touched

| File | Role |
|---|---|
| `data/raw.json` | Source of truth — all incidents keyed by uuid |
| `search/index.py` | Builds ChromaDB + BM25 indices from `raw.json`. Run manually. |
| `search/retriever.py` | `retrieve(query, k)` — hybrid search + RRF fusion |
| `search/writer.py` | `save_incident(summary, mitigation)` — appends new entries to `raw.json` |
| `search/chroma_db/` | Persisted ChromaDB collection (created by `index.py`) |
| `search/bm25s_index/` | Persisted BM25 index + corpus (created by `index.py`) |
| `notebook.ipynb` | Section 4: Similar Case Retrieval — demo call, rendered results |
