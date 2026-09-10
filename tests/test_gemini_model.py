from pathlib import Path

from anki_bot.gemini_review import DEFAULT_MODEL, resolve_model_name
from anki_bot.model_select import FLASH_MODEL, PRO_MODEL


def test_default_model_is_pro() -> None:
    assert DEFAULT_MODEL == PRO_MODEL
    assert resolve_model_name(None) == PRO_MODEL
    assert resolve_model_name("auto") == PRO_MODEL


def test_explicit_flash_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert resolve_model_name(FLASH_MODEL) == FLASH_MODEL
