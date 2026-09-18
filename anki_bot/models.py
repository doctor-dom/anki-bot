"""Pydantic schemas for Gemini structured output and review JSON."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    STEM = "stem"
    CHOICE = "choice"
    EXPLANATION = "explanation"
    UI = "ui"
    LECTURE = "lecture"


class ContentKind(str, Enum):
    QUESTION = "question"
    LECTURE = "lecture"


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


class CardBudgetInfo(BaseModel):
    soft_min: int
    soft_max: int
    hard_max: int
    lecture_hours: float | None = None


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_usd: float = 0.0
    model: str = ""


class SourceFileFingerprint(BaseModel):
    """Portable source identity: relpath + sha256; legacy path + mtime_ns still supported."""

    size: int
    relpath: str = ""
    sha256: str = ""
    path: str = ""
    mtime_ns: int = 0


class QuestionReview(BaseModel):
    """Canonical editable review document for one question or lecture."""

    id: str
    kind: ContentKind = ContentKind.QUESTION
    item: ItemInfo
    stem_clues: list[str] = Field(default_factory=list)
    correct_pearl: str = ""
    distractors: list[Distractor] = Field(default_factory=list)
    high_yield: list[HighYieldItem] = Field(default_factory=list)
    cards: list[ClozeCard] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_images: list[str] = Field(default_factory=list)
    source_html: list[str] = Field(default_factory=list)
    source_pdfs: list[str] = Field(default_factory=list)
    processed_at: str = ""
    topic: str = ""
    track: str = ""
    source_fingerprint: list[SourceFileFingerprint] = Field(default_factory=list)
    card_budget: CardBudgetInfo | None = None
    usage: UsageInfo | None = None


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
    *,
    kind: ContentKind = ContentKind.QUESTION,
    source_images: list[str] | None = None,
    source_html: list[str] | None = None,
    source_pdfs: list[str] | None = None,
) -> QuestionReview:
    return QuestionReview(
        id=question_id,
        kind=kind,
        item=response.item,
        stem_clues=response.stem_clues,
        correct_pearl=response.correct_pearl,
        distractors=response.distractors,
        high_yield=response.high_yield,
        cards=response.cards,
        warnings=response.warnings,
        source_images=source_images or [],
        source_html=source_html or [],
        source_pdfs=source_pdfs or [],
        processed_at=utc_now_iso(),
    )


def topic_heading(review: QuestionReview) -> str:
    for item in review.high_yield:
        if item.category == Category.TOPIC:
            return item.text
    if review.item.correct_text:
        return review.item.correct_text
    return review.item.stem_gist[:80] or review.id
