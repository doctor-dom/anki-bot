from pathlib import Path

from anki_bot.gemini_review import review_images_from_fixture
from anki_bot.html_render import render_high_yield_page, render_item_preview, write_high_yield_html
from anki_bot.models import ContentKind, ItemInfo, QuestionReview
from anki_bot.outputs import sort_qbank_reviews
FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def test_high_yield_html_contains_colors() -> None:
    review = review_images_from_fixture("sample", [], FIXTURE)
    html = render_high_yield_page([review])
    assert "hy-topic" in html
    assert "hy-neg" in html
    assert "hy-dx" in html
    assert "21-hydroxylase deficiency" in html


def test_high_yield_html_embeds_figures() -> None:
    review = QuestionReview(
        id="12-endocrine",
        kind=ContentKind.QUESTION,
        item=ItemInfo(stem_gist="x", correct_text="CAH"),
        high_yield=[{"text": "CAH", "category": "topic", "source": "stem"}],
        source_images=["/unused"],
    )
    html = render_high_yield_page(
        [review],
        include_figures=True,
        media_by_review={"12-endocrine": ["12-endocrine-0.png"]},
    )
    assert 'src="media/12-endocrine-0.png"' in html


def test_qbank_sort_by_topic_then_number() -> None:
    a = QuestionReview(id="13-cardio", kind=ContentKind.QUESTION, item=ItemInfo(stem_gist="c"))
    b = QuestionReview(id="12-endocrine", kind=ContentKind.QUESTION, item=ItemInfo(stem_gist="e"))
    ordered = sort_qbank_reviews([a, b])
    assert [r.id for r in ordered] == ["13-cardio", "12-endocrine"]


def test_preview_figures_use_relative_media() -> None:
    review = QuestionReview(
        id="q1",
        kind=ContentKind.QUESTION,
        item=ItemInfo(stem_gist="x"),
        high_yield=[{"text": "pearl", "category": "topic", "source": "stem"}],
    )
    html = render_item_preview(review, media_by_review={"q1": ["q1-0.png"]})
    assert 'src="../media/q1-0.png"' in html


def test_write_high_yield_file(tmp_path: Path) -> None:
    review = review_images_from_fixture("sample", [], FIXTURE)
    out = tmp_path / "high-yield.html"
    write_high_yield_html([review], out)
    text = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "hy-diff" in text
