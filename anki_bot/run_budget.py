"""Optional wall-clock budget for long ``anki-bot run`` sessions (e.g. NightBot)."""

from __future__ import annotations

import os
import time

_run_started_at: float | None = None


def mark_run_started() -> None:
    global _run_started_at
    _run_started_at = time.monotonic()


def run_budget_exceeded() -> bool:
    raw = os.getenv("ANKI_BOT_RUN_BUDGET_MINUTES", "").strip()
    if not raw or _run_started_at is None:
        return False
    try:
        limit_minutes = float(raw)
    except ValueError:
        return False
    if limit_minutes <= 0:
        return False
    elapsed_minutes = (time.monotonic() - _run_started_at) / 60.0
    return elapsed_minutes >= limit_minutes
