from pathlib import Path

from anki_bot.discover import ContentGroup
from anki_bot.models import ContentKind, SourceFileFingerprint
from anki_bot.processed import (
    attach_fingerprint,
    fingerprint_group,
    fingerprints_match,
    should_skip_group,
)
from anki_bot.models import ItemInfo, QuestionReview


def test_fingerprint_stable_across_parent_path(tmp_path: Path) -> None:
    root_a = tmp_path / "input"
    root_b = tmp_path / "mirror" / "input"
    root_a.mkdir(parents=True)
    root_b.mkdir(parents=True)
    content = b"same pdf bytes"
    path_a = root_a / "abp" / "1 - topic.pdf"
    path_b = root_b / "abp" / "1 - topic.pdf"
    path_a.parent.mkdir(parents=True)
    path_b.parent.mkdir(parents=True)
    path_a.write_bytes(content)
    path_b.write_bytes(content)

    group_a = ContentGroup(
        id="1-topic",
        kind=ContentKind.QUESTION,
        pdf_paths=(path_a,),
        track="abp",
    )
    group_b = ContentGroup(
        id="1-topic",
        kind=ContentKind.QUESTION,
        pdf_paths=(path_b,),
        track="abp",
    )

    fp_a = fingerprint_group(group_a, input_roots=[root_a])
    fp_b = fingerprint_group(group_b, input_roots=[root_b])
    assert fingerprints_match(fp_a, fp_b)


def test_legacy_fingerprint_matches_hash(tmp_path: Path) -> None:
    pdf = tmp_path / "input" / "q.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"question content here")
    group = ContentGroup(id="q", kind=ContentKind.QUESTION, pdf_paths=(pdf,))
    current = fingerprint_group(group, input_roots=[tmp_path / "input"])

    legacy = [
        SourceFileFingerprint(
            path=str(pdf.resolve()),
            size=pdf.stat().st_size,
            mtime_ns=999,
        )
    ]
    assert fingerprints_match(legacy, current)


def test_skip_after_rename(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    pdf = input_root / "1 - item.pdf"
    pdf.write_bytes(b"%PDF content")
    output = tmp_path / "output"
    group = ContentGroup(
        id="1-item",
        kind=ContentKind.QUESTION,
        pdf_paths=(pdf,),
        track="misc",
    )
    review = attach_fingerprint(
        QuestionReview(id="1-item", kind=ContentKind.QUESTION, item=ItemInfo(stem_gist="x")),
        group,
        input_roots=[input_root],
    )
    review_path = output / "reviews" / "1-item.json"
    review_path.parent.mkdir(parents=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    moved = input_root / "batch" / "1 - item.pdf"
    moved.parent.mkdir()
    moved.write_bytes(b"%PDF content")
    group_moved = ContentGroup(
        id="1-item",
        kind=ContentKind.QUESTION,
        pdf_paths=(moved,),
        track="misc",
    )
    assert should_skip_group(
        group_moved,
        review_path,
        input_roots=[input_root],
    )
