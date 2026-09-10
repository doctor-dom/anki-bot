"""Validate cloze cards before export."""

from __future__ import annotations

import re

from anki_bot.models import ClozeCard, QuestionReview

CLOZE_PATTERN = re.compile(r"\{\{c\d+::.+?\}\}", re.DOTALL)
MAX_CARD_TEXT_LEN = 400
MAX_CARDS_DEFAULT = 5


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
