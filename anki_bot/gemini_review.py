"""Gemini API: extract grounded review JSON from screenshots and lecture HTML."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from anki_bot.card_budget import CardBudget
from anki_bot.discover import ContentGroup
from anki_bot.html_extract import combine_lecture_html
from anki_bot.model_select import PRO_MODEL, normalize_model
from anki_bot.models import (
    CardBudgetInfo,
    ContentKind,
    GeminiReviewResponse,
    QuestionReview,
    UsageInfo,
    review_from_gemini,
)
from anki_bot.usage import UsageRecord, usage_from_metadata

DEFAULT_MODEL = PRO_MODEL
TUTOR_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "tutor.md"
LECTURE_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "lecture.md"

ACCURACY_ADDENDUM = """
## Accuracy over coverage

Prefer accuracy over hitting the card count range. Never invent facts not shown in the source.
Omit unclear facts. One atomic grounded cloze per card. Do not pad to reach the target range.
Fewer excellent cards beats filling the quota.
"""


def load_prompt(path: Path, fallback: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def load_tutor_prompt() -> str:
    return load_prompt(TUTOR_PROMPT_PATH, "Extract grounded teaching points from the screenshots only.")


def load_lecture_prompt() -> str:
    return load_prompt(
        LECTURE_PROMPT_PATH,
        "Extract grounded teaching points from the lecture HTML only.",
    )


def _mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(ext, "image/png")


def _image_part(path: Path) -> types.Part:
    data = path.read_bytes()
    return types.Part.from_bytes(data=data, mime_type=_mime_type(path))


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return genai.Client(api_key=api_key)


def resolve_model_name(model: str | None = None) -> str:
    """Default to Pro; only honor explicit model overrides."""
    if model and model.strip().lower() not in {"", "auto", "default"}:
        return normalize_model(model)
    env_model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    if env_model.strip().lower() in {"", "auto", "default"}:
        return DEFAULT_MODEL
    return normalize_model(env_model)


def _budget_instruction(budget: CardBudget) -> str:
    return (
        f"\n\nTarget cloze cards: {budget.prompt_range()} when enough grounded material exists."
    )


def _call_gemini(
    client: genai.Client,
    model_name: str,
    parts: list[types.Part | str],
) -> tuple[GeminiReviewResponse, UsageRecord | None]:
    schema = GeminiReviewResponse.model_json_schema()
    model_name = normalize_model(model_name)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=parts,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=schema,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True,
                ),
            ),
        )
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "Could not reach the Gemini API (DNS/network error). "
            "Check your internet connection, VPN, firewall, or try another network. "
            "Test in PowerShell: Resolve-DnsName generativelanguage.googleapis.com"
        ) from exc
    except genai_errors.ClientError as exc:
        if exc.status_code == 404 and "gemini-2.5-pro" in str(exc):
            raise RuntimeError(
                f"Model {model_name!r} is not available on your API key. "
                f"anki-bot now uses {PRO_MODEL!r} by default."
            ) from exc
        raise RuntimeError(f"Gemini API error ({exc.status_code}): {exc}") from exc
    raw = response.text or ""
    try:
        payload = json.loads(raw)
        parsed = GeminiReviewResponse.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError(f"Gemini returned invalid JSON: {exc}\nRaw: {raw[:500]}") from exc

    usage = usage_from_metadata(getattr(response, "usage_metadata", None), model=model_name)
    return parsed, usage


def _attach_metadata(
    review: QuestionReview,
    *,
    budget: CardBudget,
    usage: UsageRecord | None,
    model_name: str,
    topic: str = "",
    track: str = "",
) -> QuestionReview:
    updates: dict = {
        "topic": topic,
        "track": track,
        "card_budget": CardBudgetInfo(
            soft_min=budget.soft_min,
            soft_max=budget.soft_max,
            hard_max=budget.hard_max,
            lecture_hours=budget.lecture_hours,
        ),
    }
    if usage is not None:
        updates["usage"] = UsageInfo(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_usd=usage.estimated_usd,
            model=usage.model or model_name,
        )
    return review.model_copy(update=updates)


def review_images(
    question_id: str,
    image_paths: list[Path],
    *,
    model: str | None = None,
    budget: CardBudget | None = None,
    track: str = "",
    client: genai.Client | None = None,
) -> QuestionReview:
    """Send screenshots to Gemini and return structured review."""
    if not image_paths:
        raise ValueError("No images provided")

    from anki_bot.card_budget import budget_for_question

    client = client or get_client()
    model_name = resolve_model_name(model)
    card_budget = budget or budget_for_question()

    parts: list[types.Part | str] = [
        load_tutor_prompt(),
        ACCURACY_ADDENDUM,
        _budget_instruction(card_budget),
        "\n\nAnalyze these question screenshot(s). Return JSON matching the schema exactly.",
    ]
    for path in image_paths:
        parts.append(_image_part(path))

    parsed, usage = _call_gemini(client, model_name, parts)
    review = review_from_gemini(
        question_id,
        parsed,
        kind=ContentKind.QUESTION,
        source_images=[str(p.resolve()) for p in image_paths],
    )
    return _attach_metadata(
        review,
        budget=card_budget,
        usage=usage,
        model_name=model_name,
        track=track,
    )


def review_lecture_html(
    lecture_id: str,
    html_paths: list[Path],
    *,
    model: str | None = None,
    budget: CardBudget | None = None,
    track: str = "",
    client: genai.Client | None = None,
) -> QuestionReview:
    """Send lecture HTML to Gemini and return structured review."""
    if not html_paths:
        raise ValueError("No HTML files provided")

    from anki_bot.card_budget import budget_for_lecture

    client = client or get_client()
    model_name = resolve_model_name(model)
    lecture_text, extract_warnings, meta = combine_lecture_html(
        html_paths,
        group_id=lecture_id,
    )
    if not lecture_text.strip():
        raise RuntimeError(
            f"No extractable text in HTML file(s): {', '.join(p.name for p in html_paths)}"
        )

    if budget is None:
        card_budget, budget_warnings = budget_for_lecture(
            lecture_hours=meta.hours,
            char_count=len(lecture_text),
        )
        review_warnings = budget_warnings
    else:
        card_budget = budget
        review_warnings = []

    parts: list[types.Part | str] = [
        load_lecture_prompt(),
        ACCURACY_ADDENDUM,
        _budget_instruction(card_budget),
        "\n\nAnalyze this lecture text extracted from HTML. Return JSON matching the schema exactly.",
        f"\n\n--- LECTURE TEXT ---\n{lecture_text}\n--- END LECTURE TEXT ---",
    ]

    parsed, usage = _call_gemini(client, model_name, parts)
    review = review_from_gemini(
        lecture_id,
        parsed,
        kind=ContentKind.LECTURE,
        source_html=[str(p.resolve()) for p in html_paths],
    )
    review.warnings.extend(extract_warnings)
    review.warnings.extend(review_warnings)
    topic = meta.topic or ""
    return _attach_metadata(
        review,
        budget=card_budget,
        usage=usage,
        model_name=model_name,
        topic=topic,
        track=track,
    )


def review_content(
    group: ContentGroup,
    *,
    model: str | None = None,
    budget: CardBudget | None = None,
    client: genai.Client | None = None,
) -> QuestionReview:
    if group.kind == ContentKind.LECTURE:
        return review_lecture_html(
            group.id,
            list(group.html_paths),
            model=model,
            budget=budget,
            track=group.track,
            client=client,
        )
    return review_images(
        group.id,
        list(group.image_paths),
        model=model,
        budget=budget,
        track=group.track,
        client=client,
    )


def review_from_fixture(
    group: ContentGroup,
    fixture_path: Path,
    *,
    budget: CardBudget | None = None,
) -> QuestionReview:
    """Load review from a JSON fixture (for tests / offline use)."""
    from anki_bot.card_budget import budget_for_group
    from anki_bot.html_extract import combine_lecture_html

    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if "item" in payload and "id" in payload:
        review = QuestionReview.model_validate(payload)
    else:
        parsed = GeminiReviewResponse.model_validate(payload)
        source_images = [str(p.resolve()) for p in group.image_paths]
        source_html = [str(p.resolve()) for p in group.html_paths]
        review = review_from_gemini(
            group.id,
            parsed,
            kind=group.kind,
            source_images=source_images,
            source_html=source_html,
        )

    if budget is None:
        lecture_hours = None
        char_count = 0
        if group.kind == ContentKind.LECTURE and group.html_paths:
            text, _, meta = combine_lecture_html(list(group.html_paths), group_id=group.id)
            lecture_hours = meta.hours
            char_count = len(text)
        budget, budget_warnings = budget_for_group(
            group.kind,
            lecture_hours=lecture_hours,
            char_count=char_count,
        )
        review.warnings.extend(budget_warnings)

    topic = review.topic
    if not topic and group.kind == ContentKind.LECTURE:
        from anki_bot.outputs import topic_from_group_id

        topic = topic_from_group_id(group.id)

    return _attach_metadata(
        review,
        budget=budget,
        usage=None,
        model_name=DEFAULT_MODEL,
        topic=topic,
        track=group.track,
    )


def review_images_from_fixture(
    question_id: str,
    image_paths: list[Path],
    fixture_path: Path,
) -> QuestionReview:
    group = ContentGroup(id=question_id, kind=ContentKind.QUESTION, image_paths=tuple(image_paths))
    return review_from_fixture(group, fixture_path)
