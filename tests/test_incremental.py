from pathlib import Path

import pytest

from anki_bot.pipeline import process_path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_lecture_review.json"
HTML_FIXTURE = Path(__file__).parent / "fixtures" / "sample_lecture.html"


def test_skip_unchanged_lecture(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    html = input_dir / "01-adrenal-lecture.html"
    html.write_bytes(HTML_FIXTURE.read_bytes())
    output = tmp_path / "output"

    process_path(input_dir, output, review_only=True, fixture=FIXTURE)
    process_path(input_dir, output, review_only=True)
    out = capsys.readouterr().out
    assert "Ignored" in out
    assert "01-adrenal-lecture" in out

    process_path(input_dir, output, review_only=True, fixture=FIXTURE, force=True)
    out_force = capsys.readouterr().out
    assert "Ran (1)" in out_force
