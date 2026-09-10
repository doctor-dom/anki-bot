"""Orchestrate discover → Gemini → validate → write outputs."""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from anki_bot.apkg import write_apkg
from anki_bot.card_budget import budget_for_group
from anki_bot.cards import filter_valid_cards
from anki_bot.discover import ContentGroup, discover_content
from anki_bot.gemini_review import review_content, review_from_fixture
from anki_bot.html_extract import combine_lecture_html
from anki_bot.html_render import write_high_yield_html, write_item_preview
from anki_bot.models import ContentKind, QuestionReview, UsageInfo
from anki_bot.outputs import packs_for_reviews, reviews_for_pack
from anki_bot.usage import UsageRecord, format_run_total, format_usage_line

load_dotenv()


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
) -> QuestionReview:
    budget, _ = _compute_group_budget(group, max_cards=max_cards)

    if fixture:
        review = review_from_fixture(group, fixture, budget=budget)
    else:
        review = review_content(group, model=model, budget=budget)

    review = filter_valid_cards(review, max_cards=max_cards)

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
    reviews: list[QuestionReview],
    output_root: Path,
    *,
    review_only: bool,
) -> list[Path]:
    written: list[Path] = []
    for pack in packs_for_reviews(output_root, reviews):
        pack_reviews = reviews_for_pack(reviews, pack)
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
) -> list[QuestionReview]:
    """Process all question groups under input_path."""
    groups = discover_content(input_path)
    if not groups:
        raise FileNotFoundError(
            f"No supported inputs found under {input_path} "
            "(expected PNG/JPG screenshots or .html lecture files)"
        )

    processed: list[QuestionReview] = []
    for group in groups:
        review = _process_group(
            group,
            output_root,
            model=model,
            max_cards=max_cards,
            fixture=fixture,
        )
        processed.append(review)

    all_reviews = load_all_reviews(reviews_dir(output_root))
    _write_output_packs(all_reviews, output_root, review_only=review_only)
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

    for pack in packs_for_reviews(output_root, all_reviews):
        pack_reviews = reviews_for_pack(all_reviews, pack)
        write_high_yield_html(pack_reviews, pack.html_path)
        total_notes += write_apkg(pack_reviews, pack.apkg_path, deck_name=pack.deck_name)

    return all_reviews, total_notes
