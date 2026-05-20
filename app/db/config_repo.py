"""Operator config access (S6). Versioned: a save appends a new version (W5),
old versions are retained for audit."""
from __future__ import annotations

from sqlalchemy import select

from app.config.operator_config import DEFAULT_CONFIG
from app.db.models import OperatorConfig


def current_config(session) -> tuple[int, dict]:
    """Return (version, data) of the latest operator config."""
    row = session.execute(
        select(OperatorConfig).order_by(OperatorConfig.version.desc()).limit(1)
    ).scalar_one_or_none()
    if row is None:
        return 1, dict(DEFAULT_CONFIG)
    return row.version, row.data


def save_config(session, data: dict) -> int:
    """Append a new config version. Returns the new version number."""
    row = OperatorConfig(data=data)
    session.add(row)
    session.flush()
    return row.version
