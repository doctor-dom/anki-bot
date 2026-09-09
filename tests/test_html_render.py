from pathlib import Path

from anki_bot.gemini_review import review_images_from_fixture
from anki_bot.html_render import render_high_yield_page, write_high_yield_html
FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def test_high_yield_html_contains_colors() -> None:
    review = review_images_from_fixture("sample", [], FIXTURE)
    html = render_high_yield_page([review])
    assert "hy-topic" in html
    assert "hy-neg" in html
    assert "hy-dx" in html
    assert "21-hydroxylase deficiency" in html


def test_write_high_yield_file(tmp_path: Path) -> None:
    review = review_images_from_fixture("sample", [], FIXTURE)
    out = tmp_path / "high-yield.html"
    write_high_yield_html([review], out)
    text = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "hy-diff" in text
