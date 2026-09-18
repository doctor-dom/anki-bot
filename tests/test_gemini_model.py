from pathlib import Path

from anki_bot.gemini_review import DEFAULT_MODEL, resolve_model_name
from anki_bot.model_select import AUTO_MODEL, FLASH_MODEL, PRO_MODEL, choose_model_for_question


def test_default_model_is_auto() -> None:
    assert DEFAULT_MODEL == AUTO_MODEL
    assert resolve_model_name(None) == AUTO_MODEL
    assert resolve_model_name("auto") == AUTO_MODEL


def test_explicit_flash_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert resolve_model_name(FLASH_MODEL) == FLASH_MODEL
    assert resolve_model_name(PRO_MODEL) == PRO_MODEL


def test_auto_picks_flash_for_single_pdf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    pdf = tmp_path / "1 - topic.pdf"
    pdf.write_bytes(b"pdf")
    choice = choose_model_for_question(pdf_paths=[pdf], image_paths=[], requested="auto")
    assert choice.model == FLASH_MODEL
    assert choice.auto_selected
