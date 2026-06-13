"""Query generation pipeline: converts an IncidentSummary into a ChromaDB search query."""

import json

from prototype.schemas.summary_schema import IncidentSummary
from prototype.schemas.query_schema import SearchQuery
from clients.claude_client import ClaudeClient
from clients.gemini_client import GeminiClient
from settings import settings


# --- helpers ---

def resolve_client() -> ClaudeClient | GeminiClient:
    """Return a ClaudeClient if an Anthropic API key is configured, else GeminiClient."""
    if settings.anthropic_api_key:
        return ClaudeClient()
    return GeminiClient()


def load_prompt(summary: IncidentSummary) -> tuple[str, str]:
    """Read the query generation system prompt from disk and serialize the summary as user content."""
    with open(settings.query_gen_prompt_path) as f:
        system_prompt = f.read()
    user_content = json.dumps(summary.model_dump(), indent=2)
    return system_prompt, user_content


def invoke(client: ClaudeClient | GeminiClient, system_prompt: str, user_content: str) -> SearchQuery:
    """Call the client with the given prompts and return a validated SearchQuery."""
    return client.invoke(
        prompt=user_content,
        system_prompt=system_prompt,
        response_schema=SearchQuery,
    )


# --- pipeline ---

def generate_query(summary: IncidentSummary) -> SearchQuery:
    """Run the full query generation pipeline on a validated IncidentSummary.

    Returns a SearchQuery with a keyword-dense query string ready for ChromaDB.
    """
    client = resolve_client()
    system_prompt, user_content = load_prompt(summary)
    return invoke(client, system_prompt, user_content)
