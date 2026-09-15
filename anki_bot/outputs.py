"""Labeled output paths for lecture and qbank packs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from anki_bot.models import ContentKind, QuestionReview

TRACK_NAMES = frozenset({"abp", "endo", "misc"})
ANKIDECK_DIRNAME = "ankideck"


def ankideck_dir(output_root: Path) -> Path:
    return output_root / ANKIDECK_DIRNAME


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


def normalize_track(track: str) -> str:
    lowered = (track or "misc").strip().lower()
    return lowered if lowered in TRACK_NAMES else "misc"


@dataclass(frozen=True)
class OutputPack:
    label: str
    deck_name: str
    html_path: Path
    apkg_path: Path
    pack_kind: PackKind = PackKind.LECTURE
    track: str = "misc"
    run_count: int = 0


def lecture_pack(output_root: Path, pack_id: str) -> OutputPack:
    label = slugify_label(pack_id)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=output_root / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root) / f"{label}.apkg",
        pack_kind=PackKind.LECTURE,
    )


def qbank_run_pack(output_root: Path, track: str, question_count: int) -> OutputPack:
    track_slug = normalize_track(track)
    label = f"qbank-{track_slug}{question_count}"
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=output_root / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root) / f"{label}.apkg",
        pack_kind=PackKind.QBANK_RUN,
        track=track_slug,
        run_count=question_count,
    )


def qbank_compiled_pack(output_root: Path, track: str) -> OutputPack:
    track_slug = normalize_track(track)
    label = f"qbank-{track_slug}"
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=output_root / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root) / f"{label}.apkg",
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
        if any(p.pack_kind == PackKind.LECTURE and p.label == label for p in packs):
            continue
        packs.append(lecture_pack(output_root, label))

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
    if pack.pack_kind == PackKind.LECTURE:
        return [
            r
            for r in all_reviews
            if r.kind == ContentKind.LECTURE and lecture_pack_label(r) == pack.label
        ]

    track = normalize_track(pack.track)
    questions = [
        r
        for r in all_reviews
        if r.kind == ContentKind.QUESTION and normalize_track(r.track) == track
    ]

    if pack.pack_kind == PackKind.QBANK_COMPILED:
        return questions

    if this_run_ids is None:
        return questions
    return [r for r in questions if r.id in this_run_ids]
