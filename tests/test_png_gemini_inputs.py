from pathlib import Path

from anki_bot.image_ocr import (
    PngInputMode,
    PngPrepareResult,
    plan_png_gemini_inputs,
    prepare_png_question_input,
)


def test_auto_sends_all_images_not_ocr_text(tmp_path: Path, monkeypatch) -> None:
    img = tmp_path / "q1.png"
    img.write_bytes(b"fake")
    body = (
        "A 10-year-old with polyuria.\n"
        "A) Wrong\nB) Another\nC) No\nD) Nope\nE) Correct\n"
        "Correct Answer: E\nExplanation: detail.\n" + ("word " * 40)
    )
    monkeypatch.setenv("ANKI_BOT_PNG_MODE", "auto")
    monkeypatch.setenv("ANKI_BOT_PNG_KEEP_OCR", "1")
    monkeypatch.setattr("anki_bot.image_ocr.tesseract_available", lambda: True)
    monkeypatch.setattr("anki_bot.image_ocr.ocr_image_text", lambda _path: body)
    prep = prepare_png_question_input([img])
    assert prep.text.strip()
    send_ocr, attach = plan_png_gemini_inputs([img], prep)
    assert send_ocr is False
    assert attach == [img]


def test_text_mode_sends_ocr_only(tmp_path: Path, monkeypatch) -> None:
    img = tmp_path / "q1.png"
    img.write_bytes(b"fake")
    body = "Stem\nA) one\nB) two\nCorrect: A\n" + ("x " * 40)
    monkeypatch.setenv("ANKI_BOT_PNG_MODE", "text")
    monkeypatch.setattr("anki_bot.image_ocr.tesseract_available", lambda: True)
    monkeypatch.setattr("anki_bot.image_ocr.ocr_image_text", lambda _path: body)
    prep = prepare_png_question_input([img], mode=PngInputMode.TEXT)
    send_ocr, attach = plan_png_gemini_inputs([img], prep)
    assert send_ocr is True
    assert attach == []


def test_text_mode_hybrid_attaches_figure_pages(tmp_path: Path, monkeypatch) -> None:
    fig = tmp_path / "12-endocrine-cxr.png"
    fig.write_bytes(b"fake")
    body = "Stem\nA) one\nCorrect: A\n" + ("x " * 40)
    monkeypatch.setenv("ANKI_BOT_PNG_MODE", "text")
    monkeypatch.setattr("anki_bot.image_ocr.tesseract_available", lambda: True)
    monkeypatch.setattr("anki_bot.image_ocr.ocr_image_text", lambda _path: body)
    monkeypatch.setattr("anki_bot.image_ocr._image_looks_like_figure", lambda _path: True)
    prep = prepare_png_question_input([fig], mode=PngInputMode.TEXT)
    send_ocr, attach = plan_png_gemini_inputs([fig], prep)
    assert send_ocr is True
    assert attach == [fig]
