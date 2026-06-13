"""Hybrid search retriever: combines ChromaDB semantic search and BM25 keyword search via RRF fusion."""

import json

import bm25s
import chromadb
from chromadb.utils import embedding_functions

from settings import settings

CANDIDATE_N_DEFAULT = 5


def _load_chroma(chroma_path: str) -> chromadb.Collection:
    """Load and return the persisted ChromaDB incidents collection from chroma_path."""
    client = chromadb.PersistentClient(path=chroma_path)
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_collection(name="incidents", embedding_function=ef)


def _load_bm25(bm25_path: str) -> bm25s.BM25:
    """Load and return the persisted BM25 index from bm25_path, including the uuid corpus."""
    return bm25s.BM25.load(bm25_path, load_corpus=True)


def _semantic_search(collection: chromadb.Collection, query: str, n: int) -> list[str]:
    """Query ChromaDB for the top-n most semantically similar incidents; return uuids in ranked order."""
    results = collection.query(query_texts=[query], n_results=n)
    return results["ids"][0]


def _bm25_search(retriever: bm25s.BM25, query: str, n: int) -> list[str]:
    """Retrieve top-n BM25 keyword matches for query; return uuids in ranked order."""
    tokens = bm25s.tokenize([query])
    results, _ = retriever.retrieve(tokens, k=n)
    return [doc["uuid"] for doc in results[0]]


def _rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Apply Reciprocal Rank Fusion across multiple ranked uuid lists; return uuids sorted by descending score.

    Score per document: sum of 1 / (k + rank_i) across all lists. k=60 is a fixed constant.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, uid in enumerate(ranking, start=1):
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda uid: scores[uid], reverse=True)


def _load_incidents(uuids: list[str], raw_path: str) -> list[dict]:
    """Load raw.json and return full records {uuid, summary, mitigation} for the given uuids, preserving order."""
    with open(raw_path) as f:
        raw = json.load(f)
    return [{"uuid": uid, **raw[uid]} for uid in uuids if uid in raw]


def retrieve(
    query: str,
    k: int = 2,
    candidate_n: int = CANDIDATE_N_DEFAULT,
    chroma_path: str = None,
    bm25_path: str = None,
    raw_path: str = None,
) -> list[dict]:
    """Run hybrid search: semantic + BM25, fused via RRF, returning the top-k incidents as [{uuid, summary, mitigation}].

    Args:
        query: The search query string (typically the generated SearchQuery text).
        k: Number of top incidents to return.
        candidate_n: Number of candidates to retrieve from each index before fusion.
        chroma_path: Override path to the ChromaDB collection directory.
        bm25_path: Override path to the BM25 index directory.
        raw_path: Override path to data/raw.json.
    """
    chroma_path = chroma_path or settings.chroma_path
    bm25_path = bm25_path or settings.bm25_path
    raw_path = raw_path or settings.raw_json_path

    collection = _load_chroma(chroma_path)
    bm25_retriever = _load_bm25(bm25_path)

    semantic_uuids = _semantic_search(collection, query, candidate_n)
    bm25_uuids = _bm25_search(bm25_retriever, query, candidate_n)

    fused = _rrf([semantic_uuids, bm25_uuids])
    top_uuids = fused[:k]

    return _load_incidents(top_uuids, raw_path)
