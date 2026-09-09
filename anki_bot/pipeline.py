"""Orchestrate discover → Gemini → validate → write outputs."""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from anki_bot.apkg import write_apkg
from anki_bot.cards import filter_valid_cards
from anki_bot.discover import QuestionGroup, discover_questions
from anki_bot.gemini_review import review_images, review_images_from_fixture
from anki_bot.html_render import write_high_yield_html, write_item_preview
from anki_bot.models import QuestionReview

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


def _process_group(
    group: QuestionGroup,
    output_root: Path,
    *,
    model: str | None,
    max_cards: int,
    fixture: Path | None,
) -> QuestionReview:
    if fixture:
        review = review_images_from_fixture(group.id, list(group.image_paths), fixture)
    else:
        review = review_images(group.id, list(group.image_paths), model=model)

    review = filter_valid_cards(review, max_cards=max_cards)

    review_json = reviews_dir(output_root) / f"{group.id}.json"
    save_review(review, review_json)
    write_item_preview(review, reviews_dir(output_root) / f"{group.id}.html")
    return review


def process_path(
    input_path: Path,
    output_root: Path,
    *,
    review_only: bool = False,
    model: str | None = None,
    max_cards: int = 10,
    deck_name: str = "HUB::anki-bot",
    fixture: Path | None = None,
) -> list[QuestionReview]:
    """Process all question groups under input_path."""
    groups = discover_questions(input_path)
    if not groups:
        raise FileNotFoundError(f"No screenshot images found under {input_path}")

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
    write_high_yield_html(all_reviews, output_root / "high-yield.html")

    if not review_only:
        apkg_path = output_root / "anki-bot.apkg"
        count = write_apkg(all_reviews, apkg_path, deck_name=deck_name)
        if count == 0:
            review = processed[-1] if processed else None
            if review:
                review.warnings.append("No valid cloze cards to pack into .apkg")

    return processed


def build_from_reviews(
    reviews_path: Path,
    output_root: Path,
    *,
    deck_name: str = "HUB::anki-bot",
    max_cards: int = 10,
) -> tuple[list[QuestionReview], int]:
    """Rebuild high-yield.html and .apkg from edited JSON files."""
    all_reviews: list[QuestionReview] = []
    for path in sorted(reviews_path.glob("*.json")):
        review = load_review(path)
        review = filter_valid_cards(review, max_cards=max_cards)
        save_review(review, path)
        write_item_preview(review, reviews_path / f"{review.id}.html")
        all_reviews.append(review)

    write_high_yield_html(all_reviews, output_root / "high-yield.html")
    count = write_apkg(all_reviews, output_root / "anki-bot.apkg", deck_name=deck_name)
    return all_reviews, count
