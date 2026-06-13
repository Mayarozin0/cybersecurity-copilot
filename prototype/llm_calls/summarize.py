"""summarization pipeline and utils"""

from prototype.schemas.summary_schema import IncidentSummary
from clients.claude_client import ClaudeClient
from clients.gemini_client import GeminiClient
from settings import settings


# --- helpers ---

def resolve_client() -> ClaudeClient | GeminiClient:
    """Return a ClaudeClient if an Anthropic API key is configured, else GeminiClient."""
    if settings.anthropic_api_key:
        return ClaudeClient()
    return GeminiClient()


def load_prompt(notes: str) -> tuple[str, str]:
    """Read the summarization system prompt from disk and return (system_prompt, notes)."""
    with open(settings.summarize_prompt_path) as f:
        system_prompt = f.read()
    return system_prompt, notes


def invoke(client: ClaudeClient | GeminiClient, system_prompt: str, notes: str) -> IncidentSummary:
    """Call the client with the given prompts and return a validated IncidentSummary."""
    return client.invoke(
        prompt=notes,
        system_prompt=system_prompt,
        response_schema=IncidentSummary,
    )


def render_summary_md(data: IncidentSummary) -> str:
    """Convert a validated IncidentSummary into a markdown string for display."""
    def fmt(val) -> str:
        if val is None:
            return "_not reported_"
        if isinstance(val, list):
            return ", ".join(val) if val else "_none_"
        return str(val)

    vc = data.vehicle_context
    atk = data.attack

    return f"""## Incident Summary

{data.summary}

---

**Date / Time:** {fmt(data.incident_datetime)}
**OEM:** {fmt(vc.oem)} · **Model:** {fmt(vc.model)} · **Year Range:** {fmt(vc.year_range)} · **Affected Vehicles:** {fmt(vc.affected_count)}

---

### Attack Profile

- **Type:** {fmt(atk.type)}
- **Vector:** {fmt(atk.vector)}
- **Entry Point:** {fmt(atk.entry_point)}
- **Target Systems:** {fmt(atk.target_systems)}
- **Affected Parts:** {fmt(atk.affected_parts)}

---

### Impact & Outcome

- **Safety Impact:** {fmt(data.safety_impact)}
- **Outcome:** {fmt(data.outcome)}

---

### Indicators of Compromise

{fmt(data.iocs)}
"""


# --- pipeline ---

def summarize(notes: str) -> tuple[IncidentSummary, str]:
    """Run the full summarization pipeline on analyst notes.

    Returns (structured IncidentSummary, rendered markdown string).
    """
    client = resolve_client()
    system_prompt, user_notes = load_prompt(notes)
    data = invoke(client, system_prompt, user_notes)
    md = render_summary_md(data)
    return data, md
