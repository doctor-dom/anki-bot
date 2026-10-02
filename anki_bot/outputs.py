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
    title: str = ""


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


@dataclass(frozen=True)
class BoardCategory:
    """Broad pediatric board bucket used for nightly topic packs."""

    key: str
    title: str
    order: int
    aliases: tuple[str, ...] = ()


# Nightly topic HTML/Anki packs use these buckets, not the fine filename topic.
BOARD_CATEGORIES: tuple[BoardCategory, ...] = (
    BoardCategory(
        key="01-adolescent-behavioral",
        title="Adolescent Medicine + STI + Sexual Health + Behavioral Health + Substance Abuse",
        order=1,
        aliases=(
            "adolescent",
            "adolescence",
            "teen",
            "sti",
            "std",
            "sexual",
            "sexual-health",
            "sexuality",
            "contraception",
            "pregnancy",
            "gynecology",
            "gynaecology",
            "behavioral",
            "behavioral-health",
            "behavioural",
            "psychiatry",
            "psych",
            "mental-health",
            "adhd",
            "autism",
            "depression",
            "anxiety",
            "suicide",
            "eating-disorder",
            "anorexia",
            "bulimia",
            "substance",
            "substance-abuse",
            "addiction",
            "opioid",
            "cannabis",
            "marijuana",
            "tobacco",
            "alcohol",
            "chlamydia",
            "gonorrhea",
            "syphilis",
            "child-abuse",
            "maltreatment",
        ),
    ),
    BoardCategory(
        key="02-allergy-heme-onc-rheum",
        title="Allergy + Immunology + Hematology + Oncology + Rheumatology",
        order=2,
        aliases=(
            "allergy",
            "allergic",
            "allergic-rhinitis",
            "anaphylaxis",
            "urticaria",
            "food-allergy",
            "immunology",
            "immune",
            "immunodeficiency",
            "hematology",
            "haematology",
            "heme",
            "heme-onc",
            "anemia",
            "sickle",
            "coagulation",
            "coagulopathy",
            "thrombosis",
            "platelet",
            "itp",
            "hemophilia",
            "neutropenia",
            "oncology",
            "onc",
            "cancer",
            "leukemia",
            "lymphoma",
            "malignancy",
            "neuroblastoma",
            "tumor",
            "rheumatology",
            "rheum",
            "jia",
            "lupus",
            "vasculitis",
            "kawasaki",
        ),
    ),
    BoardCategory(
        key="03-cardiology-pulmonology",
        title="Cardiology + Pulmonology",
        order=3,
        aliases=(
            "cardiology",
            "cardio",
            "cardiac",
            "heart",
            "murmur",
            "chd",
            "chf",
            "arrhythmia",
            "endocarditis",
            "pulmonology",
            "pulmonary",
            "pulm",
            "respiratory",
            "lung",
            "asthma",
            "pneumonia",
            "bronchiolitis",
            "cf",
            "cystic-fibrosis",
        ),
    ),
    BoardCategory(
        key="04-dermatology",
        title="Dermatology",
        order=4,
        aliases=(
            "dermatology",
            "derm",
            "skin",
            "rash",
            "eczema",
            "acne",
            "atopic-dermatitis",
            "dermatitis",
        ),
    ),
    BoardCategory(
        key="05-emergency-msk-ophtho-ent",
        title="Emergency Medicine + Orthopedics + Musculoskeletal + Ophthalmology + ENT",
        order=5,
        aliases=(
            "emergency",
            "trauma",
            "toxicology",
            "tox",
            "poisoning",
            "orthopedic",
            "orthopedics",
            "orthopaedics",
            "ortho",
            "msk",
            "musculoskeletal",
            "sports",
            "sports-med",
            "sports-medicine",
            "fracture",
            "ophthalmology",
            "ophtho",
            "ophth",
            "eye",
            "strabismus",
            "conjunctivitis",
            "ent",
            "otolaryngology",
            "otitis",
            "pharyngitis",
            "sinusitis",
            "croup",
            "epiglottitis",
        ),
    ),
    BoardCategory(
        key="06-endocrinology-metabolic-genetics",
        title="Endocrinology + Metabolic Disorders + Genetics",
        order=6,
        aliases=(
            "endocrinology",
            "endocrine",
            "endo",
            "metabolic",
            "metabolic-disorders",
            "metabolism",
            "inborn",
            "inborn-error",
            "inborn-errors",
            "genetics",
            "genetic",
            "chromosome",
            "diabetes",
            "t1dm",
            "t2dm",
            "dka",
            "thyroid",
            "adrenal",
            "cah",
            "puberty",
            "growth-hormone",
            "rickets",
            "pku",
        ),
    ),
    BoardCategory(
        key="07-gastroenterology",
        title="Gastroenterology",
        order=7,
        aliases=(
            "gastroenterology",
            "gastrointestinal",
            "gastro",
            "gi",
            "hepatology",
            "liver",
            "ibd",
            "celiac",
            "constipation",
            "gerd",
            "heartburn",
        ),
    ),
    BoardCategory(
        key="08-preventative-pediatrics",
        title="Preventative Pediatrics + Growth + Development + Vaccines + Nutrition",
        order=8,
        aliases=(
            "preventative",
            "preventive",
            "preventative-pediatrics",
            "preventive-pediatrics",
            "prevention",
            "well-child",
            "well-visit",
            "growth",
            "development",
            "developmental",
            "milestone",
            "vaccine",
            "vaccines",
            "immunization",
            "immunizations",
            "nutrition",
            "nutritional",
            "feeding",
            "obesity",
            "ftt",
            "failure-to-thrive",
        ),
    ),
    BoardCategory(
        key="09-infectious-disease",
        title="Infectious Disease",
        order=9,
        aliases=(
            "infectious-disease",
            "infectious",
            "infection",
            "id",
            "hiv",
            "sepsis",
            "meningitis",
            "osteomyelitis",
            "antibiotic",
            "antimicrobial",
        ),
    ),
    BoardCategory(
        key="10-neonatology",
        title="Neonatology",
        order=10,
        aliases=(
            "neonatology",
            "neonate",
            "neonatal",
            "newborn",
            "nicu",
            "prematurity",
            "preterm",
            "jaundice",
            "hyperbilirubinemia",
            "bilirubin",
        ),
    ),
    BoardCategory(
        key="11-nephrology",
        title="Nephrology",
        order=11,
        aliases=(
            "nephrology",
            "nephro",
            "renal",
            "kidney",
            "urology",
            "urologic",
            "uti",
            "pyelonephritis",
            "hematuria",
            "proteinuria",
        ),
    ),
    BoardCategory(
        key="12-neurology",
        title="Neurology",
        order=12,
        aliases=(
            "neurology",
            "neuro",
            "neurologic",
            "seizure",
            "epilepsy",
            "headache",
            "migraine",
            "concussion",
            "cerebral-palsy",
        ),
    ),
)

OTHER_BOARD_CATEGORY = BoardCategory(key="other", title="Other", order=99)

_BOARD_ALIAS_ROWS: tuple[tuple[tuple[str, ...], BoardCategory], ...] = tuple(
    (tuple(alias.split("-")), category)
    for category in BOARD_CATEGORIES
    for alias in category.aliases
)


def fine_topic_slug(review: QuestionReview) -> str:
    """Filename or review topic, including words after the first hyphen segment."""
    if review.topic:
        return slugify_label(review.topic)
    base = review.id
    if base.endswith("-lecture"):
        base = base[: -len("-lecture")]
    parts = base.split("-", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return slugify_label(parts[1])
    return slugify_label(base)


def _alias_in_tokens(tokens: tuple[str, ...], alias: tuple[str, ...]) -> bool:
    width = len(alias)
    if width == 0 or width > len(tokens):
        return False
    return any(tokens[index : index + width] == alias for index in range(len(tokens) - width + 1))


def match_board_category(slug: str) -> BoardCategory:
    """Map a fine topic slug onto a board category. Longer aliases win ties."""
    tokens = tuple(part for part in slug.split("-") if part)
    best: BoardCategory | None = None
    best_len = -1
    best_order = 10**9
    for alias, category in _BOARD_ALIAS_ROWS:
        matched = len(alias)
        if not _alias_in_tokens(tokens, alias):
            continue
        if matched > best_len or (matched == best_len and category.order < best_order):
            best = category
            best_len = matched
            best_order = category.order
    return best or OTHER_BOARD_CATEGORY


def board_category_for_review(review: QuestionReview) -> BoardCategory:
    return match_board_category(fine_topic_slug(review))


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


def qbank_topic_pack(
    output_root: Path,
    track: str,
    topic_key: str,
    *,
    title: str = "",
) -> OutputPack:
    track_slug = normalize_track(track)
    label = topic_key
    display = title or label
    track_root = track_output_root(output_root, track_slug)
    return OutputPack(
        label=label,
        deck_name=f"HUB::{track_slug}::{display}",
        html_path=track_root / "topics" / f"{label}-high-yield.html",
        apkg_path=ankideck_dir(output_root, track_slug) / f"{label}.apkg",
        pack_kind=PackKind.QBANK_TOPIC,
        track=track_slug,
        topic_key=topic_key,
        title=display,
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


def prune_stale_topic_files(output_root: Path, packs: list[OutputPack]) -> None:
    """Drop topic HTML and track decks that this rebuild no longer emits.

    Narrow per-filename topic packs are replaced by board-category packs. Files
    left from the previous layout would otherwise sync back to Drive.
    """
    if not output_root.is_dir():
        return

    keep_html = {pack.html_path.resolve() for pack in packs}
    keep_apkg = {pack.apkg_path.resolve() for pack in packs}
    tracks = {normalize_track(pack.track) for pack in packs}

    for child in output_root.iterdir():
        if not child.is_dir() or child.name.lower() not in tracks:
            continue
        topics_dir = child / "topics"
        if topics_dir.is_dir():
            for html_path in topics_dir.glob("*.html"):
                if html_path.resolve() not in keep_html:
                    html_path.unlink()
        deck_dir = child / ANKIDECK_DIRNAME
        if deck_dir.is_dir():
            for apkg_path in deck_dir.glob("*.apkg"):
                if apkg_path.resolve() not in keep_apkg:
                    apkg_path.unlink()


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
        categories = sorted(
            {board_category_for_review(r) for r in track_questions},
            key=lambda category: (category.order, category.key),
        )
        for category in categories:
            packs.append(
                qbank_topic_pack(
                    output_root,
                    track,
                    category.key,
                    title=category.title,
                )
            )
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
            [r for r in questions if board_category_for_review(r).key == pack.topic_key]
        )

    if pack.pack_kind == PackKind.QBANK_FOLDER:
        return sort_qbank_reviews(
            [r for r in questions if review_input_folder_key(r) == pack.folder_key]
        )

    return sort_qbank_reviews(questions)
