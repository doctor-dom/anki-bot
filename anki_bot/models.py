"""Pydantic schemas for Gemini structured output and review JSON."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    STEM = "stem"
    CHOICE = "choice"
    EXPLANATION = "explanation"
    UI = "ui"


class Category(str, Enum):
    TOPIC = "topic"
    NEG = "neg"
    DX = "dx"
    TX = "tx"
    DIFF = "diff"


CATEGORY_CSS: dict[Category, str] = {
    Category.TOPIC: "hy-topic",
    Category.NEG: "hy-neg",
    Category.DX: "hy-dx",
    Category.TX: "hy-tx",
    Category.DIFF: "hy-diff",
}


class Choice(BaseModel):
    letter: str
    text: str


class ItemInfo(BaseModel):
    stem_gist: str
    choices: list[Choice] = Field(default_factory=list)
    correct_letter: str = ""
    correct_text: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class Distractor(BaseModel):
    letter: str
    text: str
    why_tempting: str = ""
    why_wrong: str = ""
    reusable_fact: str = ""


class HighYieldItem(BaseModel):
    text: str
    category: Category
    source: SourceType


class ClozeCard(BaseModel):
    text: str
    extra: str = ""
    tags: list[str] = Field(default_factory=list)
    source: SourceType


class QuestionReview(BaseModel):
    """Canonical editable review document for one question."""

    id: str
    item: ItemInfo
    stem_clues: list[str] = Field(default_factory=list)
    correct_pearl: str = ""
    distractors: list[Distractor] = Field(default_factory=list)
    high_yield: list[HighYieldItem] = Field(default_factory=list)
    cards: list[ClozeCard] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_images: list[str] = Field(default_factory=list)
    processed_at: str = ""


class GeminiReviewResponse(BaseModel):
    """Structured response from Gemini before we attach metadata."""

    item: ItemInfo
    stem_clues: list[str] = Field(default_factory=list)
    correct_pearl: str = ""
    distractors: list[Distractor] = Field(default_factory=list)
    high_yield: list[HighYieldItem] = Field(default_factory=list)
    cards: list[ClozeCard] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def review_from_gemini(
    question_id: str,
    response: GeminiReviewResponse,
    source_images: list[str],
) -> QuestionReview:
    return QuestionReview(
        id=question_id,
        item=response.item,
        stem_clues=response.stem_clues,
        correct_pearl=response.correct_pearl,
        distractors=response.distractors,
        high_yield=response.high_yield,
        cards=response.cards,
        warnings=response.warnings,
        source_images=source_images,
        processed_at=utc_now_iso(),
    )


def topic_heading(review: QuestionReview) -> str:
    for item in review.high_yield:
        if item.category == Category.TOPIC:
            return item.text
    if review.item.correct_text:
        return review.item.correct_text
    return review.item.stem_gist[:80] or review.id
