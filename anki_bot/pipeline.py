"""Orchestrate discover → Gemini → validate → write outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from anki_bot.apkg import write_apkg
from anki_bot.card_budget import budget_for_group
from anki_bot.cards import filter_valid_cards
from anki_bot.discover import ContentGroup
from anki_bot.drive_sync import discover_with_drive
from anki_bot.gemini_review import review_content, review_from_fixture
from anki_bot.html_extract import combine_lecture_html
from anki_bot.html_render import write_high_yield_html, write_item_preview
from anki_bot.models import ContentKind, QuestionReview
from anki_bot.outputs import PackKind, packs_for_reviews, reviews_for_pack
from anki_bot.processed import attach_fingerprint, should_skip_group
from anki_bot.usage import UsageRecord, format_run_total, format_usage_line

load_dotenv()


@dataclass(frozen=True)
class RunLogEntry:
    kind: str
    group_id: str
    source_summary: str


def reviews_dir(output_root: Path) -> Path:
    return output_root / "reviews"


def load_review(path: Path) -> QuestionReview:
    data = json.loads(path.read_text(encoding="utf-8"))
    return QuestionReview.model_validate(data)


def save_review(review: QuestionReview, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(review.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_all_reviews(reviews_path: Path) -> list[QuestionReview]:
    if not reviews_path.exists():
        return []
    files = sorted(reviews_path.glob("*.json"))
    return [load_review(f) for f in files]


def _usage_record(review: QuestionReview) -> UsageRecord | None:
    if review.usage is None:
        return None
    return UsageRecord(
        input_tokens=review.usage.input_tokens,
        output_tokens=review.usage.output_tokens,
        estimated_usd=review.usage.estimated_usd,
        model=review.usage.model,
    )


def _source_summary(group: ContentGroup) -> str:
    paths = list(group.pdf_paths) + list(group.image_paths) + list(group.html_paths)
    return ", ".join(p.name for p in paths) or group.id


def _print_run_log(ran: list[RunLogEntry], ignored: list[RunLogEntry]) -> None:
    print(f"Ran ({len(ran)}):")
    if ran:
        for entry in ran:
            print(f"  {entry.kind:<8} {entry.group_id:<24} {entry.source_summary}")
    else:
        print("  (none)")

    print(f"Ignored ({len(ignored)}, unchanged):")
    if ignored:
        for entry in ignored:
            print(f"  {entry.kind:<8} {entry.group_id:<24} {entry.source_summary}")
    else:
        print("  (none)")


def _compute_group_budget(
    group: ContentGroup,
    *,
    max_cards: int | None,
):
    lecture_hours = None
    char_count = 0
    if group.kind == ContentKind.LECTURE and group.html_paths:
        text, _, meta = combine_lecture_html(list(group.html_paths), group_id=group.id)
        lecture_hours = meta.hours
        char_count = len(text)
    return budget_for_group(
        group.kind,
        lecture_hours=lecture_hours,
        char_count=char_count,
        max_cards_override=max_cards,
    )


def _process_group(
    group: ContentGroup,
    output_root: Path,
    *,
    model: str | None,
    max_cards: int | None,
    fixture: Path | None,
    input_roots: list[Path] | None = None,
) -> QuestionReview:
    budget, _ = _compute_group_budget(group, max_cards=max_cards)

    if fixture:
        review = review_from_fixture(group, fixture, budget=budget)
    else:
        review = review_content(group, model=model, budget=budget)

    review = filter_valid_cards(review, max_cards=max_cards)
    review = attach_fingerprint(review, group, input_roots=input_roots)
    if not review.track:
        review = review.model_copy(update={"track": group.track})

    review_json = reviews_dir(output_root) / f"{group.id}.json"
    save_review(review, review_json)
    write_item_preview(review, reviews_dir(output_root) / f"{group.id}.html")

    usage = _usage_record(review)
    if usage is not None:
        label = review.topic or review.id
        hours = review.card_budget.lecture_hours if review.card_budget else None
        print(format_usage_line(label, usage, lecture_hours=hours))

    return review


def _write_output_packs(
    all_reviews: list[QuestionReview],
    output_root: Path,
    *,
    review_only: bool,
    this_run_reviews: list[QuestionReview] | None = None,
) -> list[Path]:
    written: list[Path] = []
    this_run_ids = frozenset(r.id for r in (this_run_reviews or []))

    for pack in packs_for_reviews(
        output_root,
        all_reviews,
        this_run_reviews=this_run_reviews,
    ):
        pack_reviews = reviews_for_pack(
            all_reviews,
            pack,
            this_run_ids=this_run_ids if pack.pack_kind == PackKind.QBANK_RUN else None,
        )
        if not pack_reviews and pack.pack_kind != PackKind.LECTURE:
            continue
        write_high_yield_html(pack_reviews, pack.html_path)
        written.append(pack.html_path)
        if not review_only:
            count = write_apkg(pack_reviews, pack.apkg_path, deck_name=pack.deck_name)
            if count == 0:
                for review in pack_reviews:
                    review.warnings.append("No valid cloze cards to pack into .apkg")
            else:
                written.append(pack.apkg_path)
                print(f"Wrote: {pack.apkg_path}")
    return written


def _print_run_summary(reviews: list[QuestionReview]) -> None:
    usages = [_usage_record(r) for r in reviews]
    usage_records = [u for u in usages if u is not None]
    if not usage_records:
        return

    lecture_hours = sum(
        (r.card_budget.lecture_hours or 0.0)
        for r in reviews
        if r.kind == ContentKind.LECTURE and r.card_budget and r.card_budget.lecture_hours
    )
    print(format_run_total(usage_records, lecture_hours=lecture_hours))


def process_path(
    input_path: Path,
    output_root: Path,
    *,
    review_only: bool = False,
    model: str | None = None,
    max_cards: int | None = None,
    deck_name: str = "HUB::anki-bot",  # noqa: ARG001 - kept for CLI compatibility
    fixture: Path | None = None,
    force: bool = False,
) -> list[QuestionReview]:
    """Process all question groups under input_path."""
    groups, input_roots, drive_warnings = discover_with_drive(input_path)
    for warning in drive_warnings:
        print(f"Warning: {warning}")
    if not groups:
        raise FileNotFoundError(
            f"No supported inputs found under {input_path} "
            "(expected PDF qbanks, PNG/JPG screenshots, or .html lecture files)"
        )

    ran: list[RunLogEntry] = []
    ignored: list[RunLogEntry] = []
    processed: list[QuestionReview] = []

    for group in groups:
        review_path = reviews_dir(output_root) / f"{group.id}.json"
        kind_label = group.kind.value
        summary = _source_summary(group)

        if (
            should_skip_group(
                group,
                review_path,
                force=force,
                input_roots=input_roots,
            )
            and fixture is None
        ):
            ignored.append(RunLogEntry(kind_label, group.id, summary))
            continue

        review = _process_group(
            group,
            output_root,
            model=model,
            max_cards=max_cards,
            fixture=fixture,
            input_roots=input_roots,
        )
        processed.append(review)
        ran.append(RunLogEntry(kind_label, group.id, summary))

    _print_run_log(ran, ignored)

    all_reviews = load_all_reviews(reviews_dir(output_root))
    _write_output_packs(
        all_reviews,
        output_root,
        review_only=review_only,
        this_run_reviews=processed,
    )
    _print_run_summary(processed)
    return processed


def build_from_reviews(
    reviews_path: Path,
    output_root: Path,
    *,
    deck_name: str = "HUB::anki-bot",  # noqa: ARG001 - kept for CLI compatibility
    max_cards: int | None = None,
) -> tuple[list[QuestionReview], int]:
    """Rebuild labeled high-yield HTML and .apkg files from edited JSON."""
    all_reviews: list[QuestionReview] = []
    total_notes = 0

    for path in sorted(reviews_path.glob("*.json")):
        review = load_review(path)
        review = filter_valid_cards(review, max_cards=max_cards)
        save_review(review, path)
        write_item_preview(review, reviews_path / f"{review.id}.html")
        all_reviews.append(review)

    for pack in packs_for_reviews(output_root, all_reviews, this_run_reviews=None):
        pack_reviews = reviews_for_pack(all_reviews, pack)
        if not pack_reviews and pack.pack_kind != PackKind.LECTURE:
            continue
        write_high_yield_html(pack_reviews, pack.html_path)
        total_notes += write_apkg(pack_reviews, pack.apkg_path, deck_name=pack.deck_name)

    return all_reviews, total_notes
