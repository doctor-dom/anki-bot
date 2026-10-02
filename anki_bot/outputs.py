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
    LECTURE_COMPILED = "lecture_compiled"
    QBANK_ALL = "qbank_all"
    QBANK_TOPIC = "qbank_topic"
    QBANK_FOLDER = "qbank_folder"


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
    topic_key: str = ""
    folder_key: str = ""


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


def parse_numbered_topic_from_id(review_id: str) -> tuple[int | None, str | None]:
    """Parse ``12-endocrine`` / ``10-t1dm-honeymoon`` style ids."""
    base = review_id
    if base.endswith("-lecture"):
        base = base[: -len("-lecture")]
    parts = base.split("-", 2)
    if len(parts) >= 2 and parts[0].isdigit():
        return int(parts[0]), parts[1]
    return None, None


def topic_key_for_review(review: QuestionReview) -> str:
    if review.topic:
        return slugify_label(review.topic)
    _number, parsed = parse_numbered_topic_from_id(review.id)
    if parsed:
        return slugify_label(parsed)
    return "other"


def qbank_sort_key(review: QuestionReview) -> tuple[str, int, str]:
    number, parsed_topic = parse_numbered_topic_from_id(review.id)
    topic = slugify_label(review.topic) if review.topic else (parsed_topic or "")
    topic_key = topic.lower() if topic else "zzz-other"
    return (topic_key, number if number is not None else 999999, review.id.lower())


def topic_heading_for_sort_key(topic_key: str) -> str:
    if topic_key == "zzz-other":
        return "Other"
    return topic_key.replace("-", " ").title()


def sort_qbank_reviews(reviews: list[QuestionReview]) -> list[QuestionReview]:
    return sorted(reviews, key=qbank_sort_key)


def sort_lecture_reviews(reviews: list[QuestionReview]) -> list[QuestionReview]:
    return sorted(reviews, key=lambda r: (lecture_pack_label(r), r.id.lower()))


def _folder_key_from_relpath(relpath: str, track: str) -> str | None:
    normalized = relpath.replace("\\", "/").strip("/")
    if "/" not in normalized:
        return None
    parent = normalized.rsplit("/", 1)[0]
    track_slug = normalize_track(track)
    parts = parent.split("/")
    if parts and parts[0].lower() == track_slug:
        parts = parts[1:]
    if not parts:
        return None
    return "/".join(parts)


def review_input_folder_key(review: QuestionReview) -> str | None:
    """Input folder path under the track (e.g. ``abp-qbank-10``), or None at track root."""
    track = normalize_track(review.track)
    for entry in review.source_fingerprint:
        if entry.relpath:
            key = _folder_key_from_relpath(entry.relpath, track)
            if key:
                return key

    for raw in (*review.source_images, *review.source_pdfs, *review.source_html):
        if not raw:
            continue
        path = Path(raw)
        parent_name = path.parent.name.lower()
        if not parent_name or parent_name == track:
            continue
        if parent_name in {"input", "screenshots", "images", "qbank-html"}:
            continue
        return slugify_label(path.parent.name)
    return None


def qbank_all_pack(output_root: Path, track: str) -> OutputPack:
    track_slug = normalize_track(track)
    label = f"all-{track_slug}"
    track_root = track_output_root(output_root, track_slug)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=track_root / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root, track_slug) / f"{label}.apkg",
        pack_kind=PackKind.QBANK_ALL,
        track=track_slug,
    )


def qbank_topic_pack(output_root: Path, track: str, topic_key: str) -> OutputPack:
    track_slug = normalize_track(track)
    label = topic_key
    track_root = track_output_root(output_root, track_slug)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{track_slug}::{label}",
        html_path=track_root / "topics" / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root, track_slug) / f"{label}.apkg",
        pack_kind=PackKind.QBANK_TOPIC,
        track=track_slug,
        topic_key=topic_key,
    )


def qbank_folder_pack(output_root: Path, track: str, folder_key: str) -> OutputPack:
    track_slug = normalize_track(track)
    folder_path = track_output_root(output_root, track_slug) / Path(folder_key)
    label = slugify_label(Path(folder_key).name)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{track_slug}::{folder_key.replace('/', '::')}",
        html_path=folder_path / f"{label}-high-yield.html",
        apkg_path=folder_path / ANKIDECK_DIRNAME / f"{label}.apkg",
        pack_kind=PackKind.QBANK_FOLDER,
        track=track_slug,
        folder_key=folder_key,
    )


def lecture_compiled_pack(output_root: Path, track: str) -> OutputPack:
    track_slug = normalize_track(track)
    label = f"lectures-{track_slug}"
    track_root = track_output_root(output_root, track_slug)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{label}",
        html_path=track_root / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root, track_slug) / f"{label}.apkg",
        pack_kind=PackKind.LECTURE_COMPILED,
        track=track_slug,
    )


def cleanup_legacy_qbank_artifacts(output_root: Path) -> None:
    """Remove per-question HTML and old qbank-* compiled/run deliverables."""
    if not output_root.is_dir():
        return

    for json_path in iter_review_json_paths(output_root):
        html_path = json_path.with_suffix(".html")
        if html_path.is_file():
            html_path.unlink()

    for child in sorted(output_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.lower() in _OUTPUT_NON_TRACK_DIRNAMES:
            continue
        track_slug = child.name.lower()
        for html_path in child.glob("qbank-*-high-yield.html"):
            html_path.unlink(missing_ok=True)
        deck_dir = child / ANKIDECK_DIRNAME
        if deck_dir.is_dir():
            for apkg in deck_dir.glob("qbank-*.apkg"):
                apkg.unlink(missing_ok=True)


def packs_for_reviews(
    output_root: Path,
    all_reviews: list[QuestionReview],
    *,
    this_run_reviews: list[QuestionReview] | None = None,
) -> list[OutputPack]:
    del this_run_reviews  # all qbank packs are rebuilt from every review JSON each run
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
        packs.append(qbank_all_pack(output_root, track))
        track_questions = [r for r in question_reviews if normalize_track(r.track) == track]
        topic_keys = sorted({topic_key_for_review(r) for r in track_questions})
        for topic_key in topic_keys:
            packs.append(qbank_topic_pack(output_root, track, topic_key))
        folder_keys = sorted(
            {key for r in track_questions if (key := review_input_folder_key(r))}
        )
        for folder_key in folder_keys:
            packs.append(qbank_folder_pack(output_root, track, folder_key))

    lecture_tracks = sorted(
        {normalize_track(r.track) for r in all_reviews if r.kind == ContentKind.LECTURE}
    )
    for track in lecture_tracks:
        packs.append(lecture_compiled_pack(output_root, track))

    return packs


def reviews_for_pack(
    all_reviews: list[QuestionReview],
    pack: OutputPack,
    *,
    this_run_ids: frozenset[str] | None = None,
) -> list[QuestionReview]:
    del this_run_ids
    pack_track = normalize_track(pack.track)
    if pack.pack_kind == PackKind.LECTURE:
        return [
            r
            for r in all_reviews
            if r.kind == ContentKind.LECTURE
            and lecture_pack_label(r) == pack.label
            and normalize_track(r.track) == pack_track
        ]

    if pack.pack_kind == PackKind.LECTURE_COMPILED:
        lectures = [
            r
            for r in all_reviews
            if r.kind == ContentKind.LECTURE and normalize_track(r.track) == pack_track
        ]
        return sort_lecture_reviews(lectures)

    questions = [
        r
        for r in all_reviews
        if r.kind == ContentKind.QUESTION and normalize_track(r.track) == pack_track
    ]

    if pack.pack_kind == PackKind.QBANK_ALL:
        return sort_qbank_reviews(questions)

    if pack.pack_kind == PackKind.QBANK_TOPIC:
        return sort_qbank_reviews(
            [r for r in questions if topic_key_for_review(r) == pack.topic_key]
        )

    if pack.pack_kind == PackKind.QBANK_FOLDER:
        return sort_qbank_reviews(
            [r for r in questions if review_input_folder_key(r) == pack.folder_key]
        )

    return sort_qbank_reviews(questions)
