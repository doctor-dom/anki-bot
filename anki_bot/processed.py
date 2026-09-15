"""Source fingerprints and skip-if-unchanged logic."""

from __future__ import annotations

import json
from pathlib import Path

from anki_bot.discover import ContentGroup
from anki_bot.models import QuestionReview, SourceFileFingerprint


def _source_paths(group: ContentGroup) -> list[Path]:
    return list(group.image_paths) + list(group.html_paths)


def fingerprint_group(group: ContentGroup) -> list[SourceFileFingerprint]:
    entries: list[SourceFileFingerprint] = []
    for path in _sorted_fingerprint_paths(_source_paths(group)):
        stat = path.stat()
        entries.append(
            SourceFileFingerprint(
                path=str(path.resolve()),
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        )
    return entries


def _sorted_fingerprint_paths(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: str(p.resolve()).lower())


def fingerprints_match(
    stored: list[SourceFileFingerprint],
    current: list[SourceFileFingerprint],
) -> bool:
    if len(stored) != len(current):
        return False

    def key(entry: SourceFileFingerprint) -> tuple[str, int, int]:
        return (entry.path, entry.size, entry.mtime_ns)

    return sorted(stored, key=key) == sorted(current, key=key)


def should_skip_group(
    group: ContentGroup,
    review_path: Path,
    *,
    force: bool = False,
) -> bool:
    if force:
        return False
    if not review_path.is_file():
        return False

    review = QuestionReview.model_validate(json.loads(review_path.read_text(encoding="utf-8")))
    if not review.source_fingerprint:
        return False
    current = fingerprint_group(group)
    return fingerprints_match(review.source_fingerprint, current)


def attach_fingerprint(review: QuestionReview, group: ContentGroup) -> QuestionReview:
    return review.model_copy(update={"source_fingerprint": fingerprint_group(group)})
