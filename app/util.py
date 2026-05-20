"""Small shared helpers (calendar math). Day 1 = 2026-01-01."""
from __future__ import annotations

from datetime import date, timedelta

START_DATE = date(2026, 1, 1)
HISTORICAL_END_DAY = 60


def day_to_date(day: int) -> date:
    """Absolute sim day (1-based) -> calendar date."""
    return START_DATE + timedelta(days=day - 1)


def date_to_day(d: date | str) -> int:
    """Calendar date -> absolute sim day (1-based)."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return (d - START_DATE).days + 1


def phase_of(day: int) -> str:
    return "historical" if day <= HISTORICAL_END_DAY else "simulation"


def sim_day(absolute_day: int) -> int:
    """Absolute day -> sim-day (1..90). Absolute 61 = sim day 1."""
    return absolute_day - HISTORICAL_END_DAY
