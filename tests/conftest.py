"""Pytest hooks shared across the suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_drive_mirror_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests on tmp_path inputs only (ignore developer .env Drive mirrors)."""
    for key in ("ANKI_BOT_DRIVE_INPUT", "ANKI_BOT_DRIVE_OUTPUT", "ANKI_BOT_RCLONE_REMOTE"):
        monkeypatch.setenv(key, "")
