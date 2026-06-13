# Summarization Pipeline — Spec Design

## Purpose

The summarization pipeline takes free-text incident notes written by a VSOC analyst and produces a structured, validated incident summary. The output serves two consumers: the human analyst (rendered as markdown) and the mitigation pipeline (Call 2, which receives the structured JSON as input).

---

## Input

Free-text analyst notes. May include:
- Narrative descriptions of what was observed
- Raw log pastes with mixed relevant and irrelevant entries
- Fragmented bullet points or incomplete information

The pipeline must handle all of these gracefully.

---

## Output Schema

All keys are always present. Missing data is `null` — never `"unknown"`, never omitted.

```json
{
  "incident_datetime": "ISO 8601 or null",
  "vehicle_context": {
    "oem": "string or null",
    "model": "string or null",
    "year_range": "string or null",
    "affected_count": "number or null"
  },
  "attack": {
    "type": "string or null",
    "vector": "string or null",
    "entry_point": "string or null",
    "target_systems": ["array of strings or null"],
    "affected_parts": ["array of strings or null"]
  },
  "safety_impact": "string or null",
  "outcome": "string or null",
  "iocs": ["array of strings or null"],
  "summary_reasoning": "max 20 words — what to include in the summary and what to leave out",
  "summary": "3–5 sentence free-text narrative of what happened, how it unfolded, and what was found"
}
```

### Field Rationale

| Field | Why it's here |
|---|---|
| `incident_datetime` | When the incident occurred or was detected. ISO 8601 for parsability. |
| `vehicle_context` | Who was affected: OEM, model, year range, fleet size. |
| `attack.type` | Category (e.g. OTA hijack, RCE, CAN injection, key relay). |
| `attack.vector` | How the attacker reached the target (cellular, Wi-Fi, physical, supply chain). |
| `attack.entry_point` | The specific surface exploited (TCU, OBD port, update server). |
| `attack.target_systems` | Onboard systems the attack aimed at (ECU, BCM, infotainment). |
| `attack.affected_parts` | Physical or software components impacted. |
| `safety_impact` | Whether vehicle safety or control was at risk — inferable from notes. |
| `outcome` | What actually happened: blocked, succeeded, partial compromise, under investigation. |
| `iocs` | Indicators of compromise: IPs, domains, hashes, anomalous commands, etc. |
| `summary_reasoning` | ≤20 words of internal reasoning: what belongs in the summary and what to exclude. Improves summary quality by forcing a plan before writing. |
| `summary` | 3–5 sentence free-text narrative. Describes what happened, how it unfolded, and what was found — not a restatement of the structured fields above. Written for a technical analyst. |

**Not included:** `severity` — requires ground truth triage context the analyst cannot reliably provide in free text. The `outcome` and `safety_impact` fields capture what IS inferable.

---

## Pydantic Model (`schemas/summary_schema.py`)

The Pydantic model is the single source of truth for the schema. It is imported by both the prompt builder and the LLM call.

```python
from pydantic import BaseModel
from typing import Optional, List


class VehicleContext(BaseModel):
    oem: Optional[str] = None
    model: Optional[str] = None
    year_range: Optional[str] = None
    affected_count: Optional[int] = None


class AttackDetail(BaseModel):
    type: Optional[str] = None
    vector: Optional[str] = None
    entry_point: Optional[str] = None
    target_systems: Optional[List[str]] = None
    affected_parts: Optional[List[str]] = None


class IncidentSummary(BaseModel):
    incident_datetime: Optional[str] = None
    vehicle_context: VehicleContext
    attack: AttackDetail
    safety_impact: Optional[str] = None
    outcome: Optional[str] = None
    iocs: Optional[List[str]] = None
    summary_reasoning: str
    summary: str
```

---

## Response Format Enforcement

The model is constrained to return valid JSON matching the schema. No post-hoc parsing guesswork.

**Demo — Gemini 1.5 Flash:**
```python
import google.generativeai as genai
from schemas.summary_schema import IncidentSummary

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=IncidentSummary,
    )
)
response = model.generate_content(prompt)
```

**Production — Claude Sonnet 4.6 via AWS Bedrock:**
```python
import anthropic
from schemas.summary_schema import IncidentSummary

client = anthropic.AnthropicBedrock(aws_region="us-east-1")
response = client.messages.parse(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": notes}],
    output_format=IncidentSummary,
)
data = response.parsed_output  # validated IncidentSummary instance
```

---

## Response Validation

**Claude path:** `client.messages.parse(..., output_format=IncidentSummary)` already returns a validated `IncidentSummary` instance. No additional `model_validate` call is needed — the SDK enforces the schema at the call boundary. A failure here is a model failure, not a schema mismatch, and should be surfaced to the analyst.

**Gemini path (demo):** `response_schema` constrains the output but does not return a Pydantic object. Explicit validation is needed after the call:

```python
from pydantic import ValidationError
from schemas.summary_schema import IncidentSummary

def parse_and_validate(raw_json: dict) -> IncidentSummary:
    try:
        return IncidentSummary.model_validate(raw_json)
    except ValidationError as e:
        raise ValueError(f"Model response failed schema validation: {e}")
```

---

## Markdown Rendering (`utils.py`)

The `render_summary_md` function converts a validated `IncidentSummary` into a clean markdown block for display in the notebook.

```python
from schemas.summary_schema import IncidentSummary

def render_summary_md(data: IncidentSummary) -> str:
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
```

**Design notes:**
- `None` fields render as `_not reported_` — not "unknown", not blank, not omitted.
- Lists render as comma-separated strings. Empty lists render as `_none_`.
- The `summary` narrative appears first — it's the primary read. The structured fields below are supporting detail.

---

## Prompt Structure (`prompts/summarize.py` + `prompts/summarize.md`)

The system prompt lives in `prompts/summarize.md` as a standalone file. `build_prompt` reads it at call time — the prompt can be edited without touching Python.

**`prompts/summarize.md`** — system prompt content:

```
<role>
You are a VSOC (Vehicle Security Operations Center) analyst assistant. Your job is to extract and structure the key facts from an analyst's incident notes.
</role>

<rules>
- Extract only what is explicitly stated in the notes. If a field is not mentioned, set it to null.
- Do not infer, guess, or fill gaps from context.
- Analyst input may contain irrelevant details mixed with incident information. Focus only on what is relevant to the security incident.
- Before writing `summary`, fill `summary_reasoning` first: in 20 words or fewer, decide what the summary should focus on and what to leave out.
- The `summary` field must be 3–5 sentences of free-text narrative describing what happened, how it unfolded, and what was found or concluded. It must NOT restate or paraphrase the structured fields (vehicle_context, attack, iocs, etc.) — those are already captured. Write for a technical analyst audience.
- Return valid JSON matching the schema exactly.
</rules>

<example>
  <notes>
    Key fob relay theft on a 2021 BMW 3 Series. Owner's fob was inside the house. Attacker used a two-device relay to extend the fob signal across roughly 20 meters to the vehicle parked in the driveway. The passive entry system accepted the relayed handshake and unlocked the doors. Vehicle was driven away. PKES module logged anomalous RF signal events at 22:12 local time. One vehicle affected.
  </notes>
  <response>
    {
      "incident_datetime": "2024-11-08T22:12:00",
      "vehicle_context": {
        "oem": "BMW",
        "model": "3 Series",
        "year_range": "2021",
        "affected_count": 1
      },
      "attack": {
        "type": "Key Relay Attack",
        "vector": "RF relay",
        "entry_point": "Passive Keyless Entry System (PKES)",
        "target_systems": ["passive entry module"],
        "affected_parts": ["PKES receiver", "door lock actuators"]
      },
      "safety_impact": "No vehicle control interference. Theft only.",
      "outcome": "Vehicle stolen. Under investigation.",
      "iocs": ["anomalous RF signal events at 22:12", "entry without owner proximity"],
      "summary_reasoning": "Focus on relay method and theft outcome; exclude PKES technical internals not in notes.",
      "summary": "A relay attack exploited the passive keyless entry system by extending the key fob signal from inside the owner's home to the vehicle parked outside. The car accepted the spoofed proximity handshake and unlocked without the owner present. The vehicle was driven away; no deeper system compromise was detected beyond the entry module."
    }
  </response>
</example>
```

**`prompts/summarize.py`** — loader:

```python
import os

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "summarize.md")

def build_prompt(notes: str) -> tuple[str, str]:
    with open(_PROMPT_FILE) as f:
        system_prompt = f.read()
    return system_prompt, notes  # (system, user) — caller splits these
```

---

## Edge Case Handling

| Case | Handling |
|---|---|
| Field not mentioned in notes | Set to `null`. No inference. |
| Noisy input (mixed relevant/irrelevant details) | Extract only incident-relevant content. Ignore noise. |
| Ambiguous outcome | Write what is stated in `outcome`; use `null` if truly absent. |
| Multiple vehicles / fleet | Use `affected_count` for number; `vehicle_context.model` for type. |
| No IOCs mentioned | `iocs: null` — do not fabricate indicators. |

---

## Files Touched

| File | Role |
|---|---|
| `schemas/summary_schema.py` | Pydantic model — single source of truth for schema |
| `prompts/summarize.md` | System prompt content — edit this to iterate on the prompt |
| `prompts/summarize.py` | `build_prompt(notes)` — reads summarize.md, returns `(system, user)` tuple |
| `utils.py` | `render_summary_md(data: IncidentSummary) -> str` |
| `notebook.ipynb` | Section 2: Summarization Pipeline — calls, validation, rendering |
