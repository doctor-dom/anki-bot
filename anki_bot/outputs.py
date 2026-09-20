"""Labeled output paths for lecture and qbank packs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from anki_bot.models import ContentKind, QuestionReview

ANKIDECK_DIRNAME = "ankideck"
REVIEWS_DIRNAME = "reviews"
# Top-level output folders that are not track roots (legacy flat layout).
_OUTPUT_NON_TRACK_DIRNAMES = frozenset({ANKIDECK_DIRNAME, REVIEWS_DIRNAME})


def normalize_track(track: str) -> str:
    lowered = (track or "misc").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = slug.strip("-")
    return slug or "misc"


def track_output_root(output_root: Path, track: str) -> Path:
    return output_root / normalize_track(track)


def reviews_dir(output_root: Path, track: str) -> Path:
    return track_output_root(output_root, track) / REVIEWS_DIRNAME


def ankideck_dir(output_root: Path, track: str) -> Path:
    return track_output_root(output_root, track) / ANKIDECK_DIRNAME


def iter_review_json_paths(output_root: Path) -> list[Path]:
    """All review JSON paths: track subfolders plus legacy flat output/reviews/."""
    paths: list[Path] = []
    legacy = output_root / REVIEWS_DIRNAME
    if legacy.is_dir():
        paths.extend(sorted(legacy.glob("*.json")))
    if not output_root.is_dir():
        return paths
    for child in sorted(output_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.lower() in _OUTPUT_NON_TRACK_DIRNAMES:
            continue
        reviews = child / REVIEWS_DIRNAME
        if reviews.is_dir():
            paths.extend(sorted(reviews.glob("*.json")))
    return paths


class PackKind(str, Enum):
    LECTURE = "lecture"
    QBANK_COMPILED = "qbank_compiled"
    QBANK_RUN = "qbank_run"


def slugify_label(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "lecture"


def topic_from_group_id(group_id: str) -> str:
    """Short lecture pack id: strip ``-lecture`` suffix and numeric prefixes."""
    base = group_id
    if base.endswith("-lecture"):
        base = base[: -len("-lecture")]
    parts = base.split("-", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return slugify_label(parts[1])
    return slugify_label(base)


def lecture_pack_label(review: QuestionReview) -> str:
    if review.kind != ContentKind.LECTURE:
        return slugify_label(review.id)
    if review.topic:
        return slugify_label(review.topic)
    return topic_from_group_id(review.id)


@dataclass(frozen=True)
class OutputPack:
    label: str
    deck_name: str
    html_path: Path
    apkg_path: Path
    pack_kind: PackKind = PackKind.LECTURE
    track: str = "misc"
    run_count: int = 0


def lecture_pack(output_root: Path, pack_id: str, *, track: str) -> OutputPack:
    label = slugify_label(pack_id)
    track_root = track_output_root(output_root, track)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=track_root / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root, track) / f"{label}.apkg",
        pack_kind=PackKind.LECTURE,
        track=normalize_track(track),
    )


def qbank_run_pack(output_root: Path, track: str, question_count: int) -> OutputPack:
    track_slug = normalize_track(track)
    label = f"qbank-{track_slug}{question_count}"
    track_root = track_output_root(output_root, track_slug)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=track_root / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root, track_slug) / f"{label}.apkg",
        pack_kind=PackKind.QBANK_RUN,
        track=track_slug,
        run_count=question_count,
    )


def qbank_compiled_pack(output_root: Path, track: str) -> OutputPack:
    track_slug = normalize_track(track)
    label = f"qbank-{track_slug}"
    track_root = track_output_root(output_root, track_slug)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=track_root / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root, track_slug) / f"{label}.apkg",
        pack_kind=PackKind.QBANK_COMPILED,
        track=track_slug,
    )


def packs_for_reviews(
    output_root: Path,
    all_reviews: list[QuestionReview],
    *,
    this_run_reviews: list[QuestionReview] | None = None,
) -> list[OutputPack]:
    packs: list[OutputPack] = []

    for review in all_reviews:
        if review.kind != ContentKind.LECTURE:
            continue
        label = lecture_pack_label(review)
        track = normalize_track(review.track)
        if any(
            p.pack_kind == PackKind.LECTURE and p.label == label and p.track == track
            for p in packs
        ):
            continue
        packs.append(lecture_pack(output_root, label, track=track))

    question_reviews = [r for r in all_reviews if r.kind == ContentKind.QUESTION]
    tracks = sorted({normalize_track(r.track) for r in question_reviews})
    for track in tracks:
        packs.append(qbank_compiled_pack(output_root, track))

    if this_run_reviews:
        run_questions = [r for r in this_run_reviews if r.kind == ContentKind.QUESTION]
        by_track: dict[str, list[QuestionReview]] = {}
        for review in run_questions:
            track = normalize_track(review.track)
            by_track.setdefault(track, []).append(review)
        for track, reviews in sorted(by_track.items()):
            if reviews:
                packs.append(qbank_run_pack(output_root, track, len(reviews)))

    return packs


def reviews_for_pack(
    all_reviews: list[QuestionReview],
    pack: OutputPack,
    *,
    this_run_ids: frozenset[str] | None = None,
) -> list[QuestionReview]:
    pack_track = normalize_track(pack.track)
    if pack.pack_kind == PackKind.LECTURE:
        return [
            r
            for r in all_reviews
            if r.kind == ContentKind.LECTURE
            and lecture_pack_label(r) == pack.label
            and normalize_track(r.track) == pack_track
        ]

    questions = [
        r
        for r in all_reviews
        if r.kind == ContentKind.QUESTION and normalize_track(r.track) == pack_track
    ]

    if pack.pack_kind == PackKind.QBANK_COMPILED:
        return questions

    if this_run_ids is None:
        return questions
    return [r for r in questions if r.id in this_run_ids]
