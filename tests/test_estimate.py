from pathlib import Path

from anki_bot.models import ContentKind, ItemInfo, QuestionReview, UsageInfo
from anki_bot.pipeline import save_review, reviews_dir
from anki_bot.estimate import estimate_path


def test_estimate_skips_unchanged(tmp_path: Path) -> None:
    input_dir = tmp_path / "input" / "abp"
    input_dir.mkdir(parents=True)
    pdf = input_dir / "1 - sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    output = tmp_path / "output"
    from anki_bot.discover import discover_content
    from anki_bot.processed import attach_fingerprint

    group = discover_content(input_dir)[0]
    review = QuestionReview(
        id=group.id,
        kind=ContentKind.QUESTION,
        item=ItemInfo(stem_gist="x"),
        usage=UsageInfo(
            input_tokens=1000,
            output_tokens=500,
            estimated_usd=0.01,
            model="gemini-3.5-flash",
        ),
        source_pdfs=[str(pdf.resolve())],
    )
    review = attach_fingerprint(review, group)
    save_review(review, reviews_dir(output) / f"{group.id}.json")

    report = estimate_path(input_dir, output)
    assert len(report.would_skip) == 1
    assert len(report.would_run) == 0
    assert report.estimated_usd == 0.0
