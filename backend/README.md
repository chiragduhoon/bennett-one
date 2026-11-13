# BENNETT ONE — API

FastAPI service with the LangGraph agent, hybrid retrieval and the rule engine. See the [root README](../README.md) and [docs/HOW_IT_WORKS.md](../docs/HOW_IT_WORKS.md).

```bash
cp .env.example .env              # then edit
uv sync
uv run uvicorn app.main:app --port 8000   # docs: http://localhost:8000/docs
uv run pytest -q                  # rule engine + conversation memory tests (no GPU or DB needed)
uv run python -m app.eval.run     # gold-set evaluation against the running API
```

| Module | What |
|---|---|
| `app/agents/graph.py` | LangGraph agent: understand → retrieve → validate → generate → verify |
| `app/rules/engine.py` | deterministic eligibility / attendance / scholarship decisions |
| `app/retrieval/hybrid.py` | vector (Qdrant) + keyword (Postgres FTS) search fused with RRF |
| `app/ingest/` | classify → extract / OCR → chunk → version → embed |
| `app/eval/run.py` | scores answers on required facts, myths, citations and behaviour |
