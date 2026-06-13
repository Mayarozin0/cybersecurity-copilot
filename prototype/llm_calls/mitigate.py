"""Mitigation pipeline — builds prompt and calls the LLM to produce a MitigationPlan."""

import json

from prototype.schemas.summary_schema import IncidentSummary
from prototype.schemas.mitigation_schema import MitigationPlan
from clients.claude_client import ClaudeClient
from clients.gemini_client import GeminiClient
from settings import settings


# --- helpers ---

def resolve_client() -> ClaudeClient | GeminiClient:
    """Return a ClaudeClient if an Anthropic API key is configured, else GeminiClient."""
    if settings.anthropic_api_key:
        return ClaudeClient()
    return GeminiClient()


def format_case(case: dict) -> str:
    """Serialize a retrieved case dict to a human-readable string."""
    return (
        f"**UUID:** {case.get('uuid', 'N/A')}\n"
        f"**Summary:** {case.get('summary', '')}\n"
        f"**Mitigation:** {case.get('mitigation', '')}"
    )


def load_prompt(summary: IncidentSummary, similar_cases: list[dict] | None = None) -> tuple[str, str]:
    """Build the mitigation system prompt and user message.

    Returns (system_prompt, user_content). If similar_cases is empty or None,
    the cases block is omitted from the user message.
    """
    with open(settings.mitigate_prompt_path) as f:
        system_prompt = f.read()

    cases_block = (
        "\n---\n".join(format_case(c) for c in similar_cases)
        if similar_cases
        else "_No similar cases provided._"
    )
    user_content = (
        f"## Incident Summary\n{json.dumps(summary.model_dump(), indent=2)}"
        f"\n\n## Similar Past Incidents\n{cases_block}"
    )
    return system_prompt, user_content


def invoke(
    client: ClaudeClient | GeminiClient,
    system_prompt: str,
    user_content: str,
) -> MitigationPlan:
    """Call the client with the given prompts and return a validated MitigationPlan."""
    return client.invoke(
        prompt=user_content,
        system_prompt=system_prompt,
        response_schema=MitigationPlan,
    )


# --- pipeline ---

def mitigate(summary: IncidentSummary, similar_cases: list[str] | None = None) -> MitigationPlan:
    """Run the mitigation pipeline for the given incident summary.

    Args:
        summary: Validated IncidentSummary from the summarization pipeline.
        similar_cases: Optional list of markdown strings for similar past incidents.

    Returns:
        A validated MitigationPlan instance.
    """
    client = resolve_client()
    system_prompt, user_content = load_prompt(summary, similar_cases)
    return invoke(client, system_prompt, user_content)
