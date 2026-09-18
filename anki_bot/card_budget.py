"""Adaptive cloze card budgets by content kind and lecture duration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from anki_bot.models import ContentKind

QUESTION_SOFT = (1, 5)
QUESTION_HARD = 5

SHORT_LECTURE_SOFT = (15, 20)
SHORT_LECTURE_HARD = 20

LONG_LECTURE_SOFT = (20, 50)
LONG_LECTURE_HARD = 50

LONG_LECTURE_HOURS = 1.0


@dataclass(frozen=True)
class CardBudget:
    """Soft target range for Gemini prompts and hard validator ceiling."""

    soft_min: int
    soft_max: int
    hard_max: int
    lecture_hours: float | None = None

    def prompt_range(self) -> str:
        return f"{self.soft_min}–{self.soft_max} (hard maximum {self.hard_max})"


def _lecture_hour_chars() -> int:
    return int(os.getenv("ANKI_BOT_LECTURE_HOUR_CHARS", "18000"))


def _bulk_qbank_enabled() -> bool:
    return os.getenv("ANKI_BOT_BULK_QBANK", "").strip().lower() in {"1", "true", "yes"}


def budget_for_question(*, max_cards_override: int | None = None) -> CardBudget:
    if max_cards_override is not None:
        return CardBudget(
            soft_min=min(QUESTION_SOFT[0], max_cards_override),
            soft_max=min(QUESTION_SOFT[1], max_cards_override),
            hard_max=max_cards_override,
        )
    if _bulk_qbank_enabled():
        return CardBudget(soft_min=1, soft_max=3, hard_max=3)
    return CardBudget(
        soft_min=QUESTION_SOFT[0],
        soft_max=QUESTION_SOFT[1],
        hard_max=QUESTION_HARD,
    )


def budget_for_lecture(
    *,
    lecture_hours: float | None,
    char_count: int,
    max_cards_override: int | None = None,
) -> tuple[CardBudget, list[str]]:
    """Return card budget and any warnings about inferred lecture duration."""
    warnings: list[str] = []
    hours = lecture_hours

    if hours is None and char_count > 0:
        hours_per_char_block = _lecture_hour_chars()
        hours = char_count / hours_per_char_block
        warnings.append(
            f"No lecture-hours meta found; estimated {hours:.1f} hr from "
            f"{char_count:,} chars (~{hours_per_char_block:,} chars/hr)"
        )

    if max_cards_override is not None:
        return (
            CardBudget(
                soft_min=min(SHORT_LECTURE_SOFT[0], max_cards_override),
                soft_max=min(SHORT_LECTURE_SOFT[1], max_cards_override),
                hard_max=max_cards_override,
                lecture_hours=hours,
            ),
            warnings,
        )

    if hours is not None and hours >= LONG_LECTURE_HOURS:
        soft = LONG_LECTURE_SOFT
        hard = LONG_LECTURE_HARD
    else:
        soft = SHORT_LECTURE_SOFT
        hard = SHORT_LECTURE_HARD

    return (
        CardBudget(
            soft_min=soft[0],
            soft_max=soft[1],
            hard_max=hard,
            lecture_hours=hours,
        ),
        warnings,
    )


def budget_for_group(
    kind: ContentKind,
    *,
    lecture_hours: float | None = None,
    char_count: int = 0,
    max_cards_override: int | None = None,
) -> tuple[CardBudget, list[str]]:
    if kind == ContentKind.QUESTION:
        return budget_for_question(max_cards_override=max_cards_override), []
    return budget_for_lecture(
        lecture_hours=lecture_hours,
        char_count=char_count,
        max_cards_override=max_cards_override,
    )
