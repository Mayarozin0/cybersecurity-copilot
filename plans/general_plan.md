# Cybersecurity Copilot — Summary Pipeline Implementation Plan

## Context

This is a PoC assignment for Cymotive. The goal is to build a VSOC analyst copilot that takes free-text incident notes, produces a structured summary, retrieves similar past incidents, and suggests a mitigation plan. The submission requires both a working Jupyter notebook and a written architecture document.

Production target: Claude Sonnet 4.6 via AWS Bedrock.
Demo implementation: Gemini 1.5 Flash (free tier, no credit card) — notebook will include a note explaining the swap.

## Pipeline (3 LLM calls + 1 vector search)

```
[Analyst Notes (free text)]
         │
         ▼
   Call 1: Summarize
         │
         ▼
[Structured Summary JSON]
         │
         ▼
   Call 2: Generate Search Query
         │
         ▼
[Search Query String]
         │
         ▼
   Vector Search (RAG)
         │
         ▼
[Top-K Similar Incidents]
         │
         └─────────────────┐
                           ▼
                 [Summary + Similar Cases]
                           │
                           ▼
                   Call 3: Mitigate
                           │
                           ▼
                 [Mitigation Plan JSON]

Final Output: Summary + Similar Cases + Mitigation Plan
```

### Call 1 — Summarization
- Input: raw analyst incident notes (free text)
- Prompt: from `prompts/summarize.py`
- Output: structured JSON (`incident_type`, `severity`, `affected_systems`, `attack_vector`, `summary`, `indicators_of_compromise`)

### Call 2 — Query Generation
- Input: summary JSON from Call 1
- Prompt: from `prompts/query_gen.py`
- Output: a short natural-language search query string optimized for semantic retrieval
- Purpose: extract the key semantic signal from the summary for vector search

### Vector Search (RAG)
- Input: query string from Call 2
- Store: `search/` — a small ChromaDB collection of 10–20 dummy past incidents, embedded at index time
- Output: top-K similar incident records (title + description + metadata)
- Hybrid search (bonus): combine semantic (embedding) + keyword (BM25) ranking

### Call 3 — Mitigation
- Input: summary JSON (Call 1) + top-K similar cases (vector search)
- Prompt: from `prompts/mitigate.py`
- Output: structured JSON (`mitigation_steps[]`, `recommended_response`, `priority`)
- The similar cases are injected as RAG context to ground the mitigation in precedent

## Project Structure

```
cybersecurity-copilot/
├── notebook.ipynb          ← main demo notebook (sectioned)
├── utils.py                ← JSON parsing, markdown rendering helpers
├── prompts/
│   ├── summarize.py        ← Call 1: summarization prompt template
│   ├── query_gen.py        ← Call 2: search query generation prompt
│   └── mitigate.py         ← Call 3: mitigation prompt template (with RAG context)
├── search/
│   ├── index.py            ← build and persist ChromaDB collection
│   ├── retriever.py        ← query the collection, return top-K results
│   └── incidents/          ← 10–20 dummy past incident .txt or .json files
├── examples/
│   └── input/
│       ├── incident_ota_supply_chain_vw_fleet.txt
│       └── incident_rce_tcu_implant_jeep.txt
└── requirements.txt
```

## Notebook Sections

| Section | Content |
|---|---|
| 1. Setup | Imports, `GEMINI_API_KEY` config cell, client init, ChromaDB init, note about Bedrock swap |
| 2. Summarization | `summarize(text) -> dict` function, demo call, rendered output |
| 3. Query Generation | `generate_query(summary_json) -> str` function, demo call |
| 4. Similar Case Retrieval | `retrieve_similar(query, k=2) -> list` function, rendered top-K results |
| 5. Mitigation | `mitigate(summary_json, similar_cases) -> dict` function, demo call, rendered output |
| 6. End-to-End Run | Full pipeline on both example inputs — shows summary + similar cases + mitigation |

## utils.py

- `parse_json_response(raw: str) -> dict` — strips markdown code fences if present, parses JSON
- `render_summary_md(data: dict) -> str` — formats summary JSON as clean markdown
- `render_similar_cases_md(cases: list) -> str` — formats retrieved cases as a readable list
- `render_mitigation_md(data: dict) -> str` — formats mitigation JSON as clean markdown
- `load_incident(path: str) -> str` — reads a `.txt` file from `examples/input/`

## prompts/

Each file exports a single function `build_prompt(input) -> str`.

- `summarize.py` — system + user prompt: extract structured JSON summary from analyst notes
- `query_gen.py` — system + user prompt: given a summary JSON, produce a short semantic search query
- `mitigate.py` — system + user prompt: given summary JSON + similar past incidents, return a JSON mitigation plan

Prompts designed for Claude Sonnet 4.6 (production target), adapted to work with Gemini Flash.

## search/

- `index.py` — embeds 10–20 dummy incident records and persists a ChromaDB collection
- `retriever.py` — exposes `retrieve(query: str, k: int) -> list[dict]` using ChromaDB's similarity search
- Dummy incidents cover a variety of automotive cybersecurity scenario types (OTA, CAN bus, TCU, telematics, etc.)

## Key Design Note

```python
# Production: swap this for AnthropicBedrock client
# import anthropic
# client = anthropic.AnthropicBedrock(aws_region="us-east-1")
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
```

## requirements.txt

```
google-generativeai
chromadb
sentence-transformers
```

## Verification

1. `pip install -r requirements.txt`
2. Run `search/index.py` once to build the ChromaDB collection
3. Set `GEMINI_API_KEY` in the Setup cell
4. Run all notebook cells — both example inputs should produce:
   - Rendered structured summary
   - Rendered top-K similar cases
   - Rendered mitigation plan grounded in those cases
5. Confirm no raw JSON leaks into the output (all goes through `utils.py` renderers)
