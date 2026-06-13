# Mitigation Pipeline — Spec Design

## Purpose

The mitigation pipeline takes the validated `IncidentSummary` (Call 1) and the top-K similar past incidents retrieved from ChromaDB (vector search), and produces a structured mitigation plan for the VSOC analyst. The output is a markdown string ready to display directly — no further formatting needed.

---

## Input

Two components, combined into a single user message:

1. **Incident summary** — the validated `IncidentSummary` serialized to JSON
2. **Similar past incidents** — top-K markdown strings retrieved from ChromaDB, separated by `---`

User message format:
```
## Incident Summary
{summary JSON}

## Similar Past Incidents
{case_1_markdown}
---
{case_2_markdown}
```

The similar cases are grounding context. The model decides in `past_cases_analyzation` whether they are relevant before writing the mitigation. If not relevant, they are ignored.

---

## Output Schema

```json
{
  "past_cases_analyzation": "≤20 words — are the retrieved cases relevant, which ones, and why or why not",
  "mitigation_reasoning": "≤15 words — core response strategy for this specific incident",
  "mitigation": "markdown string"
}
```

The `mitigation` field is a markdown string structured with two sections:

```markdown
## Immediate Containment
- Step 1
- Step 2

## Long-Term Hardening
- Step 1
- Step 2
```

Steps are general best-practice recommendations grounded in the incident — not overly specific commands or version numbers. If a past case shaped a specific step, it may be cited inline (e.g., "as seen in similar OTA hijack cases"). If no past case is relevant, no citation appears.

---

## Pydantic Model (`schemas/mitigation_schema.py`)

```python
from pydantic import BaseModel


class MitigationPlan(BaseModel):
    past_cases_analyzation: str  # ≤20 words
    mitigation_reasoning: str    # ≤15 words
    mitigation: str              # markdown string
```

---

## Response Format Enforcement

**Demo — Gemini 1.5 Flash:**
```python
import google.generativeai as genai
from schemas.mitigation_schema import MitigationPlan

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=MitigationPlan,
    )
)
response = model.generate_content(prompt)
```

**Production — Claude Sonnet 4.6 via AWS Bedrock:**
```python
import anthropic
from schemas.mitigation_schema import MitigationPlan

client = anthropic.AnthropicBedrock(aws_region="us-east-1")
response = client.messages.parse(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": user_content}],
    output_format=MitigationPlan,
)
result = response.parsed_output  # validated MitigationPlan instance
```

---

## Response Validation

**Claude path:** `client.messages.parse(..., output_format=MitigationPlan)` returns a validated instance. No additional call needed.

**Gemini path (demo):**
```python
from pydantic import ValidationError
from schemas.mitigation_schema import MitigationPlan

def parse_and_validate(raw_json: dict) -> MitigationPlan:
    try:
        return MitigationPlan.model_validate(raw_json)
    except ValidationError as e:
        raise ValueError(f"Model response failed schema validation: {e}")
```

---

## Prompt Structure

System prompt lives in `prompts/mitigate.md`. The prompt builder lives in `utils.py`.

**`prompts/mitigate.md`** — system prompt content:

```
<role>
You are a VSOC (Vehicle Security Operations Center) analyst assistant. Your job is to produce a clear, actionable mitigation plan for a cybersecurity incident based on the structured summary and any relevant past cases.
</role>

<rules>
- First, fill `past_cases_analyzation` (≤20 words): assess whether the provided similar past incidents are relevant to this incident. Name which ones are relevant and why, or state they are not relevant.
- Then, fill `mitigation_reasoning` (≤15 words): decide the core response strategy before writing steps.
- Write `mitigation` as a markdown string with two sections: `## Immediate Containment` and `## Long-Term Hardening`.
- Steps should be general best-practice recommendations grounded in the incident details — not overly specific commands or version numbers.
- If a past case is relevant and shaped a specific step, cite it briefly inline. If no past case is relevant, do not reference them in the mitigation.
- Do not let past cases dominate or bias the mitigation if they are not closely relevant.
</rules>
```

**`utils.py`** — prompt builder:

```python
import json
from schemas.summary_schema import IncidentSummary

_MITIGATE_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "mitigate.md")

def build_mitigate_prompt(summary: IncidentSummary, similar_cases: list[str]) -> tuple[str, str]:
    with open(_MITIGATE_PROMPT_FILE) as f:
        system_prompt = f.read()
    cases_block = "\n---\n".join(similar_cases) if similar_cases else "_No similar cases retrieved._"
    user_content = (
        f"## Incident Summary\n{json.dumps(summary.model_dump(), indent=2)}"
        f"\n\n## Similar Past Incidents\n{cases_block}"
    )
    return system_prompt, user_content
```

---

## Example

**Input summary (excerpt):**
```json
{
  "attack": {
    "type": "OTA Supply Chain Compromise",
    "vector": "supply chain / rogue update server",
    "entry_point": "OTA update server",
    "target_systems": ["OTA client", "firmware update module"]
  },
  "vehicle_context": { "oem": "Volkswagen", "model": "ID.4", "affected_count": 1200 },
  "outcome": "Blocked — vehicles detected tampered firmware"
}
```

**Expected output:**
```json
{
  "past_cases_analyzation": "Case 2 relevant — same OTA vector, blocked outcome; Case 1 unrelated CAN bus attack.",
  "mitigation_reasoning": "Supply chain compromise; prioritize update integrity and server audit.",
  "mitigation": "## Immediate Containment\n- Take the OTA update server offline for forensic audit\n- Revoke and re-issue the firmware signing certificate\n- Notify affected fleet operators that no installation occurred\n\n## Long-Term Hardening\n- Enforce end-to-end signature verification on all firmware packages before delivery\n- Add integrity checks in the on-vehicle OTA client to detect tampering at download time\n- Monitor update infrastructure for unauthorized server activity (as seen in similar OTA supply chain cases)"
}
```

---

## Notebook Usage

Section 5 in `notebook.ipynb`:

```python
plan = mitigate(summary, similar_cases)  # returns MitigationPlan
display(Markdown(plan.mitigation))
```

No `render_*` function needed — `mitigation` is already a markdown string.

---

## Edge Cases

| Case | Handling |
|---|---|
| No similar cases retrieved | `similar_cases = []` → cases block renders as `_No similar cases retrieved._`; model writes mitigation from summary alone |
| Past cases not relevant | `past_cases_analyzation` states this; no citations appear in `mitigation` |
| Incident outcome is "blocked" | Mitigation still applies — containment confirms the block held; hardening prevents recurrence |
| Sparse summary (many null fields) | Model writes general best-practice steps for the known attack type; does not fabricate specifics |

---

## Files Touched

| File | Role |
|---|---|
| `schemas/mitigation_schema.py` | Pydantic model — `MitigationPlan` |
| `prompts/mitigate.md` | System prompt content — edit to iterate on the prompt |
| `utils.py` | `build_mitigate_prompt(summary, similar_cases) -> (system, user)` |
| `notebook.ipynb` | Section 5: Mitigation — demo call, `display(Markdown(plan.mitigation))` |
