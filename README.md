# Betsy — Autonomous Procurement Agent

Betsy is a single-agent (ReAct) autonomous procurement system for a small manufacturer.
She monitors inventory, evaluates suppliers on price/lead-time/reliability, generates
purchase orders, tracks deliveries, reconciles invoices, learns from outcomes, and pauses
for human approval on high-value decisions — all driven from a **Jenny dashboard** over a
90-day simulation.

Built to the architecture decided in the design docs (LangGraph + MCP tools + Gemini +
PostgreSQL/pgvector). See **[Architecture](#architecture)** for the decision mapping.

---

## Control Room — live replay (GitHub Pages)

A dark **"control-room" UI** that **replays a full 90-day run** with complete
traceability — press play or drag the day slider to watch Betsy consume stock, hit
reorder points, weigh suppliers, place POs, receive (good and bad) deliveries, catch
invoice fraud, and bank lessons, step by step. Every KPI, supplier bar, and inventory
flag updates *as of the day on the scrubber*.

**Replay (static):** https://diklinuks.github.io/Betsy--App/

It's a static React app (`web/ui/`) that reads a recorded `web/ui/public/run.json` — **no
server, no database** at view time. Pushing to `main` builds and publishes it via GitHub
Actions (`.github/workflows/deploy-pages.yml`), which **auto-enables Pages** on its first run.

### Regenerate the replay data

```bash
docker compose up -d                                # Postgres (pgvector)
python -m app.main export web/ui/public/run.json    # record a fresh run (set GEMINI_API_KEY in .env for real LLM reasoning)
cd web/ui && npm install && npm run dev             # preview the Control Room locally
```

The export resets the DB, runs the sim headless, and captures the whole event stream +
per-day snapshots into one JSON. Commit the new `run.json` and push to redeploy.

---

## Live interactive demo (Render)

The replay above is a recording. To run the **real thing** online — Gemini making each
decision, the run **pausing for your approval** on high-value POs, and **learning from your
rejections** — deploy the FastAPI app to [Render](https://render.com) with the included
[`render.yaml`](render.yaml) Blueprint:

1. **render.com → New + → Blueprint** → connect this repo → **Apply**.
2. Paste your **`GEMINI_API_KEY`** when prompted (stored as a secret).
3. First boot creates the schema, enables `pgvector`, and seeds the dataset automatically.

You get a public URL (e.g. `https://betsy.onrender.com`). The Blueprint provisions a free web
service + free Postgres. (Free tier: the service sleeps after ~15 min idle — first hit wakes
in ~45s — and the free database expires after ~30 days.)

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

## Free-tier / rate limits (Gemini)

The free tier caps requests (~15/min). To avoid `429 RESOURCE_EXHAUSTED`:
- **`BETSY_AGENT_MODE=single`** (default) — one structured LLM call per reorder. Far
  fewer requests; a full 90-day run fits the free tier. Set `BETSY_AGENT_MODE=react`
  for the full ReAct tool-calling loop over MCP (more calls — best for short demos).
- Calls are **throttled** to `BETSY_LLM_RPS` (default 0.2 ≈ 12/min) and **retry** on 429
  (`BETSY_LLM_MAX_RETRIES`). Lower the RPS if you still see 429s — the sim just runs slower.
- **Reflection** (an LLM call) fires only on *poor* outcomes (late/defect/short) + rejections,
  not on every delivery, to conserve quota.

## Notes & known limits

- Without `GEMINI_API_KEY`, decisions use a documented heuristic (weighs price/lead/score).
- Pause/Resume/Stop the run from the dashboard; click any decision row for full reasoning.
- The simulation is deterministic given the seed except for LLM choices.
