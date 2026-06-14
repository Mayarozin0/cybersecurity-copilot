# Cybersecurity Copilot (PoC)

An AI copilot for VSOC analysts. It takes free-text incident notes and produces a
structured **summary**, retrieves **similar past incidents** (hybrid semantic + keyword
search), and proposes a **mitigation plan**.

Built for the GenAI assignment in [ASSIGNMENT.md](ASSIGNMENT.md).

## Where to find what

- **Assignment brief** — [ASSIGNMENT.md](ASSIGNMENT.md)
- **Solution design & architecture** (the deliverable write-up) — [solution_design.md](solution_design.md)
- **Working prototype / demo** — [prototype/copilot.ipynb](prototype/copilot.ipynb)
- **Prompts** (summarize, query-gen, mitigate) — [prompts/](prompts/)
- **Pipeline stages** (LLM calls) — [prototype/llm_calls/](prototype/llm_calls/)
- **Hybrid retrieval** (Chroma + BM25 + RRF) — [prototype/search/](prototype/search/)
- **Pydantic output schemas** — [prototype/schemas/](prototype/schemas/)
- **Knowledge base + persisted indexes** — [data/](data/)
- **Sample inputs & outputs** — [examples/](examples/)
- **Config** — [settings.py](settings.py)

## How to run

```bash
# 1. Activate the virtual environment
source .venv/bin/activate

# 2. Install dependencies (if needed)
pip install -r requirements.txt

# 3. Set an API key in .env
#    ANTHROPIC_API_KEY=...   (preferred — uses Claude)
#    GEMINI-API-KEY=...      (fallback — uses Gemini)

# 4. Open the demo notebook
jupyter notebook prototype/copilot.ipynb
```

The notebook walks through the full pipeline end to end:
**notes → summary → query → similar incidents → mitigation plan.**

Sample analyst notes to try live in [examples/input/](examples/input/).
