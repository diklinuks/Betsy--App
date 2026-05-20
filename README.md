# Betsy — Autonomous Procurement Agent

Betsy is a single-agent (ReAct) autonomous procurement system for a small manufacturer.
She monitors inventory, evaluates suppliers on price/lead-time/reliability, generates
purchase orders, tracks deliveries, reconciles invoices, learns from outcomes, and pauses
for human approval on high-value decisions — all driven from a **Jenny dashboard** over a
90-day simulation.

Built to the architecture decided in the design docs (LangGraph + MCP tools + Gemini +
PostgreSQL/pgvector). See **[Architecture](#architecture)** for the decision mapping.

---

## Quick start

> Prerequisites: **Docker Desktop** running, **Python 3.12**, and a free
> **Gemini API key** (https://aistudio.google.com/app/apikey). Without a key the sim
> still runs using a transparent rule-based fallback.

```bash
# 1. Start PostgreSQL (with pgvector)
docker compose up -d

# 2. Python environment
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env        # then edit .env and paste your GEMINI_API_KEY

# 4. Load the dataset (static catalogs + 60 days of history -> seeds supplier scores)
python -m app.main load

# 5a. Run with the dashboard
uvicorn app.web.main:app --reload --port 8000
#     open http://localhost:8000  ->  click "Run simulation"

# 5b. ...or run headless (auto-approves escalations) and print the report
python -m app.main run
```

---

## Architecture

| Decision (design docs) | Implementation |
|---|---|
| Single ReAct agent | `app/agent/graph.py` — LangGraph `create_react_agent` |
| Tools as an **MCP server** | `app/mcp_server/server.py` (FastMCP); LangGraph consumes it via `langchain-mcp-adapters` |
| Gemini 2.5 Flash + embeddings (swappable) | `app/agent/model.py` |
| Code vs LLM split | LLM *proposes* (graph) → code *decides/enforces/writes* (`app/sim/runner.py`, `app/tools/functions.py`) |
| Memory layer (S3–S11) | `app/db/models.py` (PostgreSQL); rationale/lessons in **pgvector** |
| Supplier scoring | `app/scoring/engine.py` |
| Triggers + day-tick | `app/sim/runner.py` (Consumption → Delivery → Check → Invoice) |
| Live world-simulator | `app/sim/world.py` — outcomes from the supplier Betsy actually chose |
| 15 test scenarios | `app/sim/scenarios.py` injected at runtime |
| HITL (interrupt/approve) | runner pauses → `app/web` approval queue → resume |
| Learning (outcome-triggered) | `app/learning/` reflection + rejection bank in pgvector |
| Ethics: caps, blocked list, append-only audit, privacy projections | enforced in `tools/functions.py` + `sim/runner.py` |

### Data flow

```
Dashboard "Run" → background day-tick runner
  each sim day:  consume → receive deliveries → inventory check → invoices
  on a reorder:  LangGraph ReAct agent (MCP read tools) → structured proposal
                 code checks caps → autonomous PO  OR  pause for approval (queue)
  on outcomes:   record delivery/invoice → recompute scores → reflect (embed lesson)
```

---

## Using the dashboard

- **Dashboard** — Run / Reset&Run / Stop; live status, progress, and the **approval queue**.
- **Approve / Reject** — over-cap or flagged POs pause here; a rejection reason is required
  (it becomes a learned lesson).
- **Decisions** — the append-only audit log (trigger, candidates, choice, reasoning, who authorised).
- **Config** — Jenny's dials (caps, scoring weights, blocked suppliers); saving versions the config.
- **Report** — scorecard vs the success criteria + scenario coverage + final supplier scores.

---

## Observability (LangGraph)

- **LangGraph Studio** — `langgraph dev` (uses `langgraph.json`) for a visual, step-through graph.
- **LangSmith tracing** — set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` in `.env`.
- **Inspect the MCP server alone** — `python -m app.mcp_server.server` or `mcp dev app/mcp_server/server.py`.

If MCP setup gives trouble, set `BETSY_TOOLS_TRANSPORT=local` in `.env` to wire the identical
tools in-process (same agent, no subprocess).

---

## Tests

```bash
pytest tests/ -q          # pure logic: scoring + scenario scheduling
```

## Project structure

```
app/
  config/   settings + operator-config defaults
  db/       SQLAlchemy models, session, CSV loader, config repo
  scoring/  supplier scoring engine (pure + DB)
  tools/    the 12 tools (plain functions)
  mcp_server/  FastMCP wrapper exposing the tools
  agent/    model, prompt, schema, ReAct graph
  learning/ pgvector memory + reflection/rejection
  sim/      scenarios, world-simulator, day-tick runner
  web/      FastAPI + Jinja/HTMX dashboard
  eval/     success-criteria report
data/       synthetic dataset + generator
tests/
```

## Notes & known limits

- Without `GEMINI_API_KEY`, decisions use a documented heuristic; set the key for real LLM reasoning.
- The MCP server spawns per decision in v1 (simple, a little slow); caching is a future optimisation.
- The simulation is deterministic given the seed except for LLM choices.
