# Solution Design & Architecture — Cybersecurity Copilot

## Overview

A VSOC analyst copilot that takes free-text incident notes and produces a structured summary, retrieves similar past incidents from a knowledge base, and generates an actionable mitigation plan. Built on Claude Sonnet 4.6 via AWS Bedrock, ChromaDB hybrid search, and OpenAI embeddings — with a lightweight standalone search mode that requires no LLM calls.

---

## Full Pipeline

```
[Analyst Notes (free text)]
         │
         ▼
   Call 1: Summarize
         │
         ▼
[IncidentSummary — Pydantic JSON]
         │
         ▼
   Call 2: Query Generation
         │
         ▼
[keyword-dense query string]
         │
         ▼
   Hybrid Search
   dense: semantic embeddings
   sparse: BM25  |  fused with RRF
         │
         ▼
[Top-K Similar Incidents (summaries)]
         │
         └─────────────────────────┐
                                   ▼
                    [IncidentSummary + Similar Cases (Summary + Mitigation)]
                                   │
                                   ▼
                          Call 3: Mitigate
                                   │
                                   ▼
                          [MitigationPlan — Pydantic JSON]
                                   │
                                   ▼
                 [Final Output: Summary · Similar Cases · Mitigation]
                                   │
                    ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
                    write-back: new incident appended to knowledge base
```

### How it works

The analyst pastes their free-text investigation notes. **Call 1** extracts a validated structured summary (`IncidentSummary`) with fields for attack type, vector, entry point, affected systems, IOCs, safety impact, and outcome. Most fields are optional — missing data is `null`, never fabricated. The `summary` field is always populated regardless of how sparse the input is.

**Call 2** takes the structured summary and produces a keyword-dense retrieval query (~15 words) optimized to surface similar past incidents.

The query hits **ChromaDB hybrid search**, which combines dense semantic vectors with sparse BM25 keyword matching, fused using Reciprocal Rank Fusion (RRF). Search runs against incident summaries only; the top 2 results return both the stored summary and the stored mitigation. In the local prototype, hybrid search and RRF were implemented manually (`bm25s` + custom fusion) since ChromaDB's native hybrid search is a cloud feature.

**Call 3** receives the structured summary plus the retrieved past incidents as grounding context. It first assesses whether the retrieved cases are relevant, then generates a mitigation plan with immediate containment steps and long-term hardening recommendations. If retrieved cases are not relevant, the model writes from the summary alone without forcing citations.

After each run, the new incident (summary + mitigation) is written back to the knowledge base. Only the summary is indexed into ChromaDB for retrieval; the mitigation is stored alongside it and returned when the incident is matched. The system improves passively as analysts use it.

---

## Standalone Search Mode

```
[Analyst Query (free text)]
         │
         ▼
   Hybrid Search
   dense: semantic embeddings
   sparse: BM25  |  fused with RRF
         │
         ▼
[Top-K Incidents — stored summary + stored mitigation]
         │
         ▼
[Rendered for Analyst]
```

### How it works

The analyst types a free-text search query directly. It is embedded and sent to ChromaDB hybrid search — no LLM calls, no latency, no generation cost. Each result includes the stored incident summary and the stored mitigation from the knowledge base. The analyst can configure the number of results returned (top-K).

For known attack patterns (OTA hijacks, key relay attacks, CAN injection), stored mitigations from real past cases are often more reliable than generated ones. This mode is designed for analysts who know what they are looking for and want fast precedent retrieval.

---

## Tools & Stack

**LLM — Claude Sonnet 4.6 via AWS Bedrock.** Anthropic's models are among the strongest available for instruction-following and structured reasoning — a natural choice for a security-critical pipeline. Sonnet was chosen over Opus for cost efficiency; it delivers comparable output quality on structured extraction and mitigation tasks at significantly lower token cost. Bedrock keeps the full stack in AWS: no additional vendor, lower latency, enterprise compliance.

**Embeddings — OpenAI `text-embedding-3-small`.** OpenAI's embedding models are industry-leading in quality-to-cost ratio, and `text-embedding-3-small` is well-supported natively by ChromaDB. It is chosen over `text-embedding-3-large` because the corpus is domain-homogeneous — all incidents use the same automotive cybersecurity vocabulary. The quality gap between small and large is negligible for homogeneous corpora; small is ~6x cheaper.

**Vector DB — ChromaDB hybrid search.** Combines dense semantic vectors with sparse BM25 keyword matching, fused with RRF. Automotive cybersecurity incidents use highly specific terminology — CVE identifiers, ECU model numbers, protocol names — that dense embeddings alone can miss. Hybrid search captures both semantic similarity and exact keyword matches. ChromaDB handles the full hybrid pipeline natively in its cloud offering; 

**PoC implementation.** The working prototype uses Gemini 1.5 Flash (free tier), local ChromaDB for semantic search, `bm25s` for keyword search, and manual Reciprocal Rank Fusion. It is functionally equivalent to the production design. The LLM client is abstracted (`resolve_client()`) so swapping Gemini for Bedrock is a single environment variable change.

---

## Design Decisions & Tradeoffs

**Why a dedicated Query Generation step?**
Separation of concerns: summarization and retrieval query optimization are distinct tasks with different objectives. Keeping them in separate calls produces focused prompts and compact outputs. The tradeoff is one extra LLM call — a single combined call would give the model the full picture, but the prompt would be harder to engineer and the output significantly heavier.

**RRF vs. weighted mean fusion.**
Two common approaches to fusing dense and sparse rankings: RRF (used here) combines rankings by position, requiring no score normalization. A weighted mean with a tunable `alpha` parameter is simpler but requires scores to be on the same scale — hard to tune reliably across different query types. RRF is more robust by default.

**Sonnet vs. Opus.**
Opus would likely produce higher quality output but consumes approximately twice the tokens at higher cost. Sonnet hits the right quality/cost balance for structured extraction and mitigation generation tasks.

---

## Prompt Engineering

**XML syntax.** All prompts are written using XML tag structure (`<instructions>`, `<examples>`, `<input>`). This is the format Claude is trained on and responds to most reliably.

**Few-shot examples.** Each prompt includes 2–3 few-shot examples. This anchors the model's output format, reduces schema violations, and improves consistency — especially for edge cases like sparse analyst notes or unusual attack vectors.

**Temperature 0.** All three LLM calls run at temperature 0 to maximize determinism. For a security tool, the same incident notes should produce the same structured output as consistently as possible. It also reduces hallucination risk on factual extraction.

**System prompt / user input separation.** Each call splits into a static system message and a dynamic user message. This enables Anthropic prompt caching on the static portion — cached tokens are billed at a fraction of standard input cost, with adjustable TTL.

**Reasoning fields.** Each call includes a short chain-of-thought field before the main output (`summary_reasoning`, `query_reasoning`, `past_cases_analyzation`, `mitigation_reasoning`). These force the model to plan before generating, measurably improving output quality. Unlike native model reasoning (extended thinking), schema-constrained reasoning fields give explicit control over reasoning depth and scope.

**Edge cases.** The summarize prompt handles noisy input (a rule to extract only incident-relevant facts, plus a few-shot example burying the attack among distractors) and incomplete input (unstated fields set to `null` rather than inferred, with a deliberately sparse example).

---

## Evaluation Plan

Each stage fails differently, so each is evaluated differently — offline against a labeled set before release, and online against live traffic.

### Offline

We curate a small hand-labeled set as the source of truth: a regression gate before any prompt or model change, and the calibration set for the judge below.

- **Summarize** — a judge checks each extracted field against the original notes. This faithfulness check is how we catch hallucination (an invented CVE, OEM, or safety impact).
- **Retrieve** — **Recall@2** and **MRR** against the labeled relevant incidents. We also compare hybrid search to semantic-only and BM25-only to show it earns its complexity.
- **Mitigate** — no single correct plan exists, so we score against a rubric (containment, long-term hardening, specificity, addresses the actual vector) plus a narrow check: it must not invent incident facts or cite irrelevant past cases. Drawing on general security knowledge is expected, not a hallucination.

### The judge

The judge estimates the individual criteria; the final grade is computed deterministically in code, so the same output always scores the same. It runs on a different model than the generator (to avoid a model favoring its own work) and is calibrated against human labels.

### Online monitoring

The model version is pinned, removing silent updates as a drift source.

- **Quality / drift** — the judge runs on sampled production cases, producing accuracy snapshots over time; a downward trend signals drift. A steady drop in retrieval match-scores means incoming incidents no longer resemble the knowledge base.
- **Latency** — tracked per stage.
- **Schema failures** — Pydantic validation errors (malformed LLM output); near zero and alerted.
- **Analyst feedback** — a UI hallucination flag the analyst can raise and describe, and an editable mitigation output so we can track how often and how heavily it's rewritten.

### Hallucination & user value

Hallucination (fabricating incident facts, not using outside knowledge) is caught at four points: the summarize judge, the mitigate judge, sampled monitoring, and the analyst flag — the last feeding back into prompt improvement. **User value** is measured by how much analysts rely on the output: mitigation acceptance rate (from edit volume), flags raised, and periodic direct feedback.

### Cost

A full run is roughly 6,350 input + 870 output tokens (~7,200 total across the three stages), costing about **$0.032 (~3 cents) per run** at Sonnet rates. Since each stage's system prompt and few-shot examples are static, prompt caching bills those tokens at a fraction of standard input cost, cutting the real per-run figure well below this estimate at any meaningful volume.
