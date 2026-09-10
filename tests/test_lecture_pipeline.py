from pathlib import Path

from anki_bot.discover import discover_content
from anki_bot.models import ContentKind
from anki_bot.pipeline import process_path

LECTURE_FIXTURE = Path(__file__).parent / "fixtures" / "sample_lecture_review.json"
HTML_FIXTURE = Path(__file__).parent / "fixtures" / "sample_lecture.html"


def test_discover_html_lecture(tmp_path: Path) -> None:
    (tmp_path / "01-adrenal-lecture.html").write_bytes(HTML_FIXTURE.read_bytes())
    (tmp_path / "01-adrenal-lecture-part2.html").write_bytes(b"<html><body><p>More notes</p></body></html>")
    groups = discover_content(tmp_path)
    assert len(groups) == 1
    assert groups[0].kind == ContentKind.LECTURE
    assert groups[0].id == "01-adrenal-lecture"
    assert len(groups[0].html_paths) == 2


def test_process_lecture_with_fixture(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "01-adrenal-lecture.html").write_bytes(HTML_FIXTURE.read_bytes())
    output = tmp_path / "output"
    reviews = process_path(
        input_dir,
        output,
        review_only=False,
        fixture=LECTURE_FIXTURE,
    )
    assert len(reviews) == 1
    assert reviews[0].kind == ContentKind.LECTURE
    assert (output / "reviews" / "01-adrenal-lecture.json").exists()
    assert (output / "adrenal-high-yield.html").exists()
    assert (output / "adrenal.apkg").exists()
    assert reviews[0].card_budget is not None
    assert reviews[0].card_budget.hard_max >= 15
