"""Labeled output paths for lecture and qbank packs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from anki_bot.models import ContentKind, QuestionReview


def slugify_label(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "lecture"


def topic_from_group_id(group_id: str) -> str:
    """Derive topic slug from ids like ``01-adrenal-lecture``."""
    base = group_id
    if base.endswith("-lecture"):
        base = base[: -len("-lecture")]
    parts = base.split("-", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return slugify_label(parts[1])
    return slugify_label(base)


@dataclass(frozen=True)
class OutputPack:
    label: str
    deck_name: str
    html_path: Path
    apkg_path: Path


def lecture_pack(output_root: Path, topic: str) -> OutputPack:
    label = slugify_label(topic)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=output_root / f"{label}-high-yield.html",
        apkg_path=output_root / f"{label}.apkg",
    )


def qbank_pack(output_root: Path, question_count: int) -> OutputPack:
    label = f"qbank{question_count}"
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=output_root / f"{label}-high-yield.html",
        apkg_path=output_root / f"{label}.apkg",
    )


def packs_for_reviews(output_root: Path, reviews: list[QuestionReview]) -> list[OutputPack]:
    packs: list[OutputPack] = []
    lectures = [r for r in reviews if r.kind == ContentKind.LECTURE]
    questions = [r for r in reviews if r.kind == ContentKind.QUESTION]

    seen_topics: set[str] = set()
    for review in lectures:
        topic = review.topic or topic_from_group_id(review.id)
        label = slugify_label(topic)
        if label in seen_topics:
            continue
        seen_topics.add(label)
        packs.append(lecture_pack(output_root, label))

    if questions:
        packs.append(qbank_pack(output_root, len(questions)))

    return packs


def reviews_for_pack(reviews: list[QuestionReview], pack: OutputPack) -> list[QuestionReview]:
    if pack.label.startswith("qbank"):
        return [r for r in reviews if r.kind == ContentKind.QUESTION]

    return [
        r
        for r in reviews
        if r.kind == ContentKind.LECTURE
        and slugify_label(r.topic or topic_from_group_id(r.id)) == pack.label
    ]
