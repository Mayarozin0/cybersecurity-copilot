"""Builds ChromaDB and BM25 indices from data/raw.json. Run manually to create or rebuild all indices."""

import json

import bm25s
import chromadb
from chromadb.utils import embedding_functions

from settings import settings


def load_raw(path: str) -> dict:
    """Load and return data/raw.json as a dict keyed by uuid."""
    with open(path) as f:
        return json.load(f)


def build_chroma_index(ids: list[str], summaries: list[str], chroma_path: str) -> None:
    """Create or update a ChromaDB PersistentClient collection, upserting all incidents by uuid.

    Uses ChromaDB's default embedding function (all-MiniLM-L6-v2).
    """
    client = chromadb.PersistentClient(path=chroma_path)
    ef = embedding_functions.DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(name="incidents", embedding_function=ef)
    collection.upsert(
        ids=ids,
        documents=summaries,
        metadatas=[{"uuid": uid} for uid in ids],
    )


def build_bm25_index(ids: list[str], summaries: list[str], bm25_path: str) -> None:
    """Tokenize summaries, build a BM25 index, and persist it to bm25_path.

    Corpus stores only uuids — no data duplication.
    """
    corpus_tokens = bm25s.tokenize(summaries)
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)
    retriever.save(bm25_path, corpus=[{"uuid": uid} for uid in ids])


def build_index() -> None:
    """Entry point: load raw.json then build both ChromaDB and BM25 indices."""
    raw = load_raw(settings.raw_json_path)
    ids = list(raw.keys())
    summaries = [raw[uid]["summary"] for uid in ids]
    build_chroma_index(ids, summaries, settings.chroma_path)
    build_bm25_index(ids, summaries, settings.bm25_path)
    print(f"Indexed {len(ids)} incidents.")


if __name__ == "__main__":
    build_index()
