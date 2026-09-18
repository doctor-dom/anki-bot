"""Source fingerprints and skip-if-unchanged logic."""

from __future__ import annotations

import json
from pathlib import Path

from anki_bot.discover import ContentGroup
from anki_bot.drive_sync import fetch_drive_review, file_sha256
from anki_bot.models import QuestionReview, SourceFileFingerprint


def _source_paths(group: ContentGroup) -> list[Path]:
    return list(group.image_paths) + list(group.html_paths) + list(group.pdf_paths)


def _sorted_fingerprint_paths(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: str(p.resolve()).lower())


def _basename(entry: SourceFileFingerprint) -> str:
    if entry.relpath:
        return Path(entry.relpath).name.lower()
    if entry.path:
        return Path(entry.path).name.lower()
    return ""


def _canonical_relpath(path: Path, input_roots: list[Path]) -> str:
    resolved = path.resolve()
    for root in input_roots:
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return path.name


def fingerprint_group(
    group: ContentGroup,
    *,
    input_roots: list[Path] | None = None,
) -> list[SourceFileFingerprint]:
    roots = input_roots or []
    if not roots:
        roots = [_infer_single_root(_source_paths(group))]

    entries: list[SourceFileFingerprint] = []
    for path in _sorted_fingerprint_paths(_source_paths(group)):
        stat = path.stat()
        entries.append(
            SourceFileFingerprint(
                relpath=_canonical_relpath(path, roots),
                size=stat.st_size,
                sha256=file_sha256(path),
                path=str(path.resolve()),
                mtime_ns=stat.st_mtime_ns,
            )
        )
    return entries


def _infer_single_root(paths: list[Path]) -> Path:
    if not paths:
        return Path.cwd()
    first = paths[0].resolve()
    for parent in first.parents:
        if parent.name.lower() == "input":
            return parent
    return first.parent


def _entries_compatible(stored: SourceFileFingerprint, current: SourceFileFingerprint) -> bool:
    if stored.size != current.size:
        return False

    s_name = _basename(stored)
    c_name = _basename(current)
    if s_name != c_name:
        return False

    if stored.sha256 and current.sha256:
        return stored.sha256 == current.sha256

    if stored.sha256 or current.sha256:
        return True

    if stored.path and current.path:
        return stored.path == current.path and stored.mtime_ns == current.mtime_ns
    return stored.mtime_ns == current.mtime_ns


def fingerprints_match(
    stored: list[SourceFileFingerprint],
    current: list[SourceFileFingerprint],
) -> bool:
    if len(stored) != len(current):
        return False
    if not stored:
        return True

    remaining = list(stored)
    for current_entry in current:
        matched_index = None
        for index, stored_entry in enumerate(remaining):
            if _entries_compatible(stored_entry, current_entry):
                matched_index = index
                break
        if matched_index is None:
            return False
        remaining.pop(matched_index)
    return True


def _review_matches_group(
    review: QuestionReview,
    group: ContentGroup,
    *,
    input_roots: list[Path] | None,
) -> bool:
    if not review.source_fingerprint:
        return False
    current = fingerprint_group(group, input_roots=input_roots)
    return fingerprints_match(review.source_fingerprint, current)


def _load_local_review(review_path: Path) -> QuestionReview | None:
    if not review_path.is_file():
        return None
    try:
        return QuestionReview.model_validate(
            json.loads(review_path.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, ValueError):
        return None


def should_skip_group(
    group: ContentGroup,
    review_path: Path,
    *,
    force: bool = False,
    input_roots: list[Path] | None = None,
) -> bool:
    if force:
        return False

    current_roots = input_roots
    local = _load_local_review(review_path)
    if local is not None and _review_matches_group(local, group, input_roots=current_roots):
        return True

    remote = fetch_drive_review(group.id)
    if remote is not None and _review_matches_group(remote, group, input_roots=current_roots):
        return True

    return False


def attach_fingerprint(
    review: QuestionReview,
    group: ContentGroup,
    *,
    input_roots: list[Path] | None = None,
) -> QuestionReview:
    return review.model_copy(
        update={"source_fingerprint": fingerprint_group(group, input_roots=input_roots)}
    )
