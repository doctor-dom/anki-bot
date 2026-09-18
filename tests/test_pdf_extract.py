from anki_bot.pdf_extract import prepare_pdf_question_text


def test_prepare_pdf_uses_text_when_mcq_like(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "q.pdf"
    body = (
        "A 10-year-old with polyuria.\n"
        "A) Wrong one\nB) Another\nC) No\nD) Nope\nE) Correct answer\n"
        "Correct Answer: E\nExplanation: honeymoon phase with residual beta cells.\n"
        + ("detail " * 40)
    )
    monkeypatch.setattr(
        "anki_bot.pdf_extract.extract_pdf_text",
        lambda _path: body,
    )
    result = prepare_pdf_question_text([pdf])
    assert not result.used_vision
    assert "Correct Answer" in result.text


def test_prepare_pdf_falls_back_to_vision_on_short_text(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "q.pdf"
    monkeypatch.setattr("anki_bot.pdf_extract.extract_pdf_text", lambda _path: "too short")
    result = prepare_pdf_question_text([pdf])
    assert result.used_vision
