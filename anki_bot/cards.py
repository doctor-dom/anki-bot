"""Validate cloze cards before export."""

from __future__ import annotations

import re

from anki_bot.models import (
    CATEGORY_CSS,
    Category,
    ClozeCard,
    ContentKind,
    HighYieldItem,
    QuestionReview,
    SourceType,
)

CLOZE_PATTERN = re.compile(r"\{\{c\d+::.+?\}\}", re.DOTALL)
MAX_CARD_TEXT_LEN = 400
MAX_CARDS_DEFAULT = 5
MAX_PHRASE_LEN = 120


class CardValidationError(ValueError):
    pass


def validate_cloze_text(text: str) -> None:
    if not text.strip():
        raise CardValidationError("Card text is empty")
    if not CLOZE_PATTERN.search(text):
        raise CardValidationError("Card text must contain at least one cloze marker {{cN::...}}")
    if len(text) > MAX_CARD_TEXT_LEN:
        raise CardValidationError(
            f"Card text exceeds {MAX_CARD_TEXT_LEN} characters (likely stem dump)"
        )


def validate_card(card: ClozeCard) -> list[str]:
    issues: list[str] = []
    try:
        validate_cloze_text(card.text)
    except CardValidationError as exc:
        issues.append(str(exc))
    if not card.source:
        issues.append("Card missing source")
    return issues


def resolve_card_cap(review: QuestionReview, max_cards: int | None = None) -> int:
    if max_cards is not None:
        return max_cards
    if review.card_budget is not None:
        return review.card_budget.hard_max
    return MAX_CARDS_DEFAULT


def filter_valid_cards(
    review: QuestionReview,
    max_cards: int | None = None,
) -> QuestionReview:
    """Return a copy with invalid cards removed and warnings appended."""
    cap = resolve_card_cap(review, max_cards)
    valid: list[ClozeCard] = []
    warnings = list(review.warnings)

    for index, card in enumerate(review.cards):
        issues = validate_card(card)
        if issues:
            warnings.append(f"Card {index + 1} rejected: {'; '.join(issues)}")
            continue
        valid.append(card)
        if len(valid) >= cap:
            if len(review.cards) > cap:
                warnings.append(f"Truncated to {cap} cards (budget cap)")
            break

    return review.model_copy(update={"cards": valid, "warnings": warnings})


def _truncate_phrase(text: str, limit: int = MAX_PHRASE_LEN) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def minimum_high_yield_text(review: QuestionReview) -> str:
    if review.correct_pearl.strip():
        return _truncate_phrase(review.correct_pearl)
    if review.item.stem_gist.strip():
        return _truncate_phrase(review.item.stem_gist)
    if review.item.correct_text.strip():
        return _truncate_phrase(review.item.correct_text)
    return ""


def _cloze_from_high_yield_item(item: HighYieldItem) -> ClozeCard:
    phrase = _truncate_phrase(re.sub(r"<[^>]+>", "", item.text))
    css = CATEGORY_CSS.get(item.category, "hy-topic")
    hidden = phrase.replace("}}", "")
    return ClozeCard(
        text=f'<span class="{css}">{{{{c1::{hidden}}}}}</span>',
        extra="",
        tags=["anki-bot::phrase"],
        source=item.source,
    )


def ensure_minimum_yield(
    review: QuestionReview,
    max_cards: int | None = None,
) -> QuestionReview:
    """Guarantee at least one high-yield phrase and one valid cloze for qbank questions."""
    if review.kind != ContentKind.QUESTION:
        return review

    warnings = list(review.warnings)
    high_yield = list(review.high_yield)
    cards = list(review.cards)

    if not high_yield:
        line = minimum_high_yield_text(review)
        if line:
            high_yield.append(
                HighYieldItem(text=line, category=Category.TOPIC, source=SourceType.STEM)
            )
        else:
            warnings.append(
                "No grounded text for minimum high-yield; reprocess with --force if needed"
            )

    if not cards and high_yield:
        cap = resolve_card_cap(review, max_cards)
        for item in high_yield[:cap]:
            candidate = _cloze_from_high_yield_item(item)
            if not validate_card(candidate):
                cards.append(candidate)
                if len(cards) >= cap:
                    break
        if not cards:
            warnings.append("Could not build fallback cloze from high-yield phrases")

    if not cards:
        answer = review.item.correct_text.strip()
        if answer:
            css = CATEGORY_CSS[Category.TOPIC]
            hidden = _truncate_phrase(answer).replace("}}", "")
            cards.append(
                ClozeCard(
                    text=f'<span class="{css}">{{{{c1::{hidden}}}}}</span>',
                    extra=_truncate_phrase(review.item.stem_gist) if review.item.stem_gist else "",
                    tags=["anki-bot::answer"],
                    source=SourceType.STEM,
                )
            )

    return review.model_copy(update={"high_yield": high_yield, "cards": cards, "warnings": warnings})
