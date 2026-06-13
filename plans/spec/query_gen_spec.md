# Query Generation Pipeline — Spec Design

## Purpose

The query generation pipeline takes a validated `IncidentSummary` (from Call 1) and produces a compact, keyword-dense search query optimized for semantic retrieval over a ChromaDB collection of past automotive cybersecurity incidents. The output query is passed directly to the vector search.

---

## Input

A validated `IncidentSummary` instance serialized to JSON. The model draws from:
- `attack.type`, `attack.vector`, `attack.entry_point`, `attack.target_systems`
- `vehicle_context.oem`, `vehicle_context.model`
- `iocs` (if present)
- `outcome`, `safety_impact`

---

## Output Schema

```json
{
  "query_reasoning": "≤15 words: which fields to emphasize and why",
  "query": "short English keyword-dense query phrase"
}
```

`query_reasoning` forces a retrieval strategy decision before writing the query. `query` is passed directly to ChromaDB's `.query()`.

---

## Pydantic Model (`schemas/query_schema.py`)

```python
from pydantic import BaseModel


class SearchQuery(BaseModel):
    query_reasoning: str  # ≤15 words — which fields drive the query and why
    query: str            # ~10–20 word English keyword-dense query phrase
```

---

## Response Format Enforcement

**Demo — Gemini 1.5 Flash:**
```python
import google.generativeai as genai
from schemas.query_schema import SearchQuery

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=SearchQuery,
    )
)
response = model.generate_content(prompt)
```

**Production — Claude Sonnet 4.6 via AWS Bedrock:**
```python
import anthropic
from schemas.query_schema import SearchQuery

client = anthropic.AnthropicBedrock(aws_region="us-east-1")
response = client.messages.parse(
    model="claude-sonnet-4-6",
    max_tokens=256,
    messages=[{"role": "user", "content": user_content}],
    output_format=SearchQuery,
)
result = response.parsed_output  # validated SearchQuery instance
```

---

## Response Validation

Same pattern as the summarize pipeline:

**Claude path:** `client.messages.parse(..., output_format=SearchQuery)` returns a validated instance. No additional call needed.

**Gemini path (demo):**
```python
from pydantic import ValidationError
from schemas.query_schema import SearchQuery

def parse_and_validate(raw_json: dict) -> SearchQuery:
    try:
        return SearchQuery.model_validate(raw_json)
    except ValidationError as e:
        raise ValueError(f"Model response failed schema validation: {e}")
```

---

## Prompt Structure (`prompts/query_gen.py` + `prompts/query_gen.md`)

System prompt lives in `prompts/query_gen.md`. `build_prompt` reads it at call time.

**`prompts/query_gen.md`** — system prompt content:

```
<role>
You are a semantic search query generator for a vehicle cybersecurity incident database.
</role>

<rules>
- Your input is a structured incident summary in JSON.
- Write one compact English search query (~10–20 words) that will surface similar past incidents.
- Include all key technical terms: attack type, vector, entry point, affected systems, OEM/model if relevant.
- Do not write a sentence — write a keyword-dense query phrase.
- Before writing the query, fill query_reasoning: in 15 words or fewer, state which fields you are emphasizing and why.
</rules>
```

**`prompts/query_gen.py`** — loader:

```python
import os
import json
from schemas.summary_schema import IncidentSummary

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "query_gen.md")

def build_prompt(summary: IncidentSummary) -> tuple[str, str]:
    with open(_PROMPT_FILE) as f:
        system_prompt = f.read()
    user_content = json.dumps(summary.model_dump(), indent=2)
    return system_prompt, user_content  # (system, user) — caller splits these
```

---

## Example

**Input summary JSON (excerpt):**
```json
{
  "attack": {
    "type": "OTA Supply Chain Compromise",
    "vector": "supply chain / rogue update server",
    "entry_point": "OTA update server",
    "target_systems": ["OTA client", "firmware update module"],
    "affected_parts": ["firmware image", "update verification module"]
  },
  "vehicle_context": { "oem": "Volkswagen", "model": "ID.4", "affected_count": 1200 },
  "outcome": "Blocked — vehicles detected tampered firmware"
}
```

**Expected output:**
```json
{
  "query_reasoning": "Emphasize OTA attack vector, supply chain, VW model, firmware tampering, blocked outcome.",
  "query": "OTA supply chain firmware hijack Volkswagen ID.4 rogue update server blocked tampered"
}
```

---

## Notebook Usage

The query is a plain string — no `render_*` function needed in `utils.py`. Display directly:

```python
result = generate_query(summary)  # returns SearchQuery
print(result.query)
```

---

## Files Touched

| File | Role |
|---|---|
| `schemas/query_schema.py` | Pydantic model — `SearchQuery` |
| `prompts/query_gen.md` | System prompt content — edit to iterate on the prompt |
| `prompts/query_gen.py` | `build_prompt(summary: IncidentSummary) -> (system, user)` |
| `notebook.ipynb` | Section 3: Query Generation — demo call, printed query |
