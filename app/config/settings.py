"""Central configuration. Reads .env once and exposes typed settings."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project paths
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"

load_dotenv(ROOT_DIR / ".env")


def _get(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None:
        raise RuntimeError(f"Missing required env var: {name} (see .env.example)")
    return val


# --- LLM / embeddings ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CHAT_MODEL = os.getenv("BETSY_CHAT_MODEL", "gemini-2.5-flash")
REFLECTION_MODEL = os.getenv("BETSY_REFLECTION_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv("BETSY_EMBEDDING_MODEL", "models/gemini-embedding-001")
EMBEDDING_DIM = int(os.getenv("BETSY_EMBEDDING_DIM", "3072"))  # gemini-embedding-001 native dim

# --- Database ---
# Managed hosts (Render, Railway, Heroku, …) hand out URLs like
# "postgres://…" or "postgresql://…". SQLAlchemy needs the psycopg3 driver
# spelled out ("postgresql+psycopg://…"), so normalise whatever we're given.
_DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://betsy:betsy@localhost:5433/betsy")
if _DB_URL.startswith("postgres://"):
    _DB_URL = "postgresql+psycopg://" + _DB_URL[len("postgres://"):]
elif _DB_URL.startswith("postgresql://"):
    _DB_URL = "postgresql+psycopg://" + _DB_URL[len("postgresql://"):]
DATABASE_URL = _DB_URL

# --- Simulation window (matches data/generate.py) ---
HISTORICAL_END_DAY = 60
SIM_END_DAY = 150           # absolute day; sim days 1..90 = absolute 61..150
SIM_DAYS = SIM_END_DAY - HISTORICAL_END_DAY  # 90

# --- Tool transport: "mcp" (decided architecture) or "local" (fallback if MCP
#     setup gives trouble — same tools wired as in-process LangChain tools) ---
TOOLS_TRANSPORT = os.getenv("BETSY_TOOLS_TRANSPORT", "mcp")

# --- Agent mode ---
#   "single" (default): ONE structured LLM call per reorder — free-tier friendly,
#            far fewer requests, won't hit the daily/RPM quota on a full 90-day run.
#   "react":  full ReAct tool-calling loop over the MCP tools (more calls; best for
#            short demos / showing the LangGraph+MCP loop, but heavy on free tier).
AGENT_MODE = os.getenv("BETSY_AGENT_MODE", "single")

# --- LLM rate limiting (Gemini free tier ~15 req/min). Throttle to avoid 429s. ---
LLM_RPS = float(os.getenv("BETSY_LLM_RPS", "0.2"))   # requests/sec (~12/min)
LLM_MAX_RETRIES = int(os.getenv("BETSY_LLM_MAX_RETRIES", "6"))

# --- Pacing: pause between sim days so the run advances smoothly instead of
#     blasting through many days at once (eases CPU + makes progress visible). ---
DAY_DELAY_SECONDS = float(os.getenv("BETSY_DAY_DELAY", "0.5"))

# --- Reasoning / budget guards ---
MAX_REACT_STEPS = 8         # hard cap on tool-call cycles per decision
REFLECTION_MAX_ITERS = 2    # high-stakes reflection iterations
SCORING_WINDOW = 20         # last N deliveries for KPI rolling window
RETRIEVAL_TOP_K = 5         # semantic memory top-k (Budget: <8)
