"""Copy input images for Anki decks and HTML outputs."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from anki_bot.models import ContentKind, QuestionReview, SourceType

_EXPLANATION_NAME = re.compile(
    r"(explanation|explain|answer|stats|overview|correct\s*answer)",
    re.IGNORECASE,
)
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _path_is_image(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_EXTENSIONS


def filter_qbank_image_paths(paths: list[str]) -> list[Path]:
    """Drop explanation/stats UI screenshots; keep stem/part/figure pages."""
    resolved = [Path(p) for p in paths if p and Path(p).is_file() and _path_is_image(Path(p))]
    if not resolved:
        return []

    kept = [p for p in resolved if not _EXPLANATION_NAME.search(p.stem)]
    return kept if kept else resolved


def source_image_paths(review: QuestionReview) -> list[Path]:
    if not review.source_images:
        return []
    if review.kind == ContentKind.QUESTION:
        return filter_qbank_image_paths(review.source_images)
    return [Path(p) for p in review.source_images if Path(p).is_file() and _path_is_image(Path(p))]


def media_basenames_for_review(review: QuestionReview) -> list[tuple[Path, str]]:
    """Return (source path, unique basename) for each image in this review."""
    entries: list[tuple[Path, str]] = []
    for index, path in enumerate(source_image_paths(review)):
        suffix = path.suffix.lower() or ".png"
        basename = f"{review.id}-{index}{suffix}"
        entries.append((path.resolve(), basename))
    return entries


def target_card_index(review: QuestionReview) -> int:
    for index, card in enumerate(review.cards):
        if review.kind == ContentKind.LECTURE and card.source == SourceType.LECTURE:
            return index
        if card.source == SourceType.STEM:
            return index
    return 0


def append_image_tags(extra: str, basenames: list[str]) -> str:
    if not basenames:
        return extra
    tags = "".join(f'<img src="{name}">' for name in basenames)
    extra = (extra or "").strip()
    if extra:
        return f"{extra}\n{tags}"
    return tags


def sync_media_for_reviews(
    reviews: list[QuestionReview],
    media_dir: Path,
) -> dict[str, list[str]]:
    """Copy images into media_dir; return review id -> basenames."""
    media_dir.mkdir(parents=True, exist_ok=True)
    by_review: dict[str, list[str]] = {}
    for review in reviews:
        names: list[str] = []
        for source, basename in media_basenames_for_review(review):
            dest = media_dir / basename
            if not dest.exists() or dest.stat().st_size != source.stat().st_size:
                shutil.copy2(source, dest)
            names.append(basename)
        if names:
            by_review[review.id] = names
    return by_review


def track_media_dir(output_root: Path, track: str) -> Path:
    from anki_bot.outputs import track_output_root

    return track_output_root(output_root, track) / "media"
