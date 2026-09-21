from pathlib import Path

from anki_bot.image_ocr import (
    PngInputMode,
    prepare_png_question_input,
    recovered_choice_letters,
)
from anki_bot.pdf_extract import looks_like_mcq


def _mcq_body() -> str:
    return (
        "A 10-year-old with polyuria.\n"
        "A) Wrong one\nB) Another\nC) No\nD) Nope\nE) Correct answer\n"
        "Correct Answer: E\nExplanation: honeymoon phase with residual beta cells.\n"
        + ("detail " * 40)
    )


def test_prepare_png_uses_text_when_mcq_like(tmp_path: Path, monkeypatch) -> None:
    img = tmp_path / "q1-part1.png"
    img.write_bytes(b"fake")
    monkeypatch.setattr(
        "anki_bot.image_ocr.tesseract_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "anki_bot.image_ocr.ocr_image_text",
        lambda _path: _mcq_body(),
    )
    result = prepare_png_question_input([img])
    assert result.used_ocr
    assert not result.used_vision
    assert result.text
    assert looks_like_mcq(result.text)


def test_prepare_png_falls_back_to_vision_on_short_ocr(tmp_path: Path, monkeypatch) -> None:
    img = tmp_path / "q1.png"
    img.write_bytes(b"fake")
    monkeypatch.setattr("anki_bot.image_ocr.tesseract_available", lambda: True)
    monkeypatch.setattr("anki_bot.image_ocr.ocr_image_text", lambda _path: "too short")
    result = prepare_png_question_input([img])
    assert result.used_vision
    assert result.vision_paths == (img,)


def test_prepare_png_hybrid_for_figure_name(tmp_path: Path, monkeypatch) -> None:
    img = tmp_path / "12-endocrine-cxr.png"
    img.write_bytes(b"fake")
    monkeypatch.setattr("anki_bot.image_ocr.tesseract_available", lambda: True)
    monkeypatch.setattr("anki_bot.image_ocr.ocr_image_text", lambda _path: _mcq_body())
    monkeypatch.setattr("anki_bot.image_ocr._image_looks_like_figure", lambda _path: True)
    result = prepare_png_question_input([img])
    assert result.text
    assert img in result.vision_paths


def test_configure_tesseract_windows_path(tmp_path: Path, monkeypatch) -> None:
    import sys
    import types

    fake = tmp_path / "tesseract.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("ANKI_BOT_TESSERACT_CMD", str(fake))
    inner = types.SimpleNamespace(tesseract_cmd="")
    monkeypatch.setitem(sys.modules, "pytesseract", types.SimpleNamespace(pytesseract=inner))

    import anki_bot.image_ocr as mod

    mod._tesseract_configured = False
    assert mod.configure_tesseract()
    assert inner.tesseract_cmd == str(fake)


def test_prepare_png_missing_tesseract_auto_vision(tmp_path: Path, monkeypatch) -> None:
    img = tmp_path / "q1.png"
    img.write_bytes(b"fake")
    monkeypatch.setattr("anki_bot.image_ocr.tesseract_available", lambda: False)
    result = prepare_png_question_input([img], mode=PngInputMode.AUTO)
    assert result.used_vision
    assert "Tesseract" in result.warnings[0]


def test_recovered_choice_letters() -> None:
    text = "A) one\nB) two\n(C) three\nCorrect: D"
    assert recovered_choice_letters(text) >= {"A", "B", "C"}
