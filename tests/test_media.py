from pathlib import Path

from anki_bot.media import filter_qbank_image_paths, media_basenames_for_review
from anki_bot.models import ContentKind, ItemInfo, QuestionReview


def test_filter_qbank_skips_explanation_pngs(tmp_path: Path) -> None:
    stem = tmp_path / "1.png"
    explain = tmp_path / "explanation.png"
    stem.write_bytes(b"\x89PNG\r\n\x1a\n")
    explain.write_bytes(b"\x89PNG\r\n\x1a\n")
    kept = filter_qbank_image_paths([str(stem), str(explain)])
    assert kept == [stem]


def test_filter_qbank_keeps_all_when_only_explanation(tmp_path: Path) -> None:
    explain = tmp_path / "answer-stats.png"
    explain.write_bytes(b"\x89PNG\r\n\x1a\n")
    kept = filter_qbank_image_paths([str(explain)])
    assert kept == [explain]


def test_media_basenames_unique_per_review(tmp_path: Path) -> None:
    img = tmp_path / "slide.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    review = QuestionReview(
        id="12-endocrine",
        kind=ContentKind.QUESTION,
        item=ItemInfo(stem_gist="x"),
        source_images=[str(img)],
    )
    entries = media_basenames_for_review(review)
    assert entries == [(img.resolve(), "12-endocrine-0.png")]
