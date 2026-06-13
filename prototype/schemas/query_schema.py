"""Pydantic schema for the query generation pipeline output."""

from pydantic import BaseModel


class SearchQuery(BaseModel):
    """Structured output from the query generation LLM call."""

    query_reasoning: str  # ≤15 words — which fields drive the query and why
    query: str            # ~10–20 word English keyword-dense query phrase
