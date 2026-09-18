"""Gemini API: extract grounded review JSON from screenshots and lecture HTML."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from PIL import Image
from pydantic import ValidationError

from anki_bot.card_budget import CardBudget
from anki_bot.discover import ContentGroup
from anki_bot.html_extract import combine_lecture_html
from anki_bot.model_select import (
    AUTO_MODEL,
    FLASH_MODEL,
    PRO_MODEL,
    ModelChoice,
    choose_model_for_lecture,
    choose_model_for_question,
    normalize_model,
)
from anki_bot.models import (
    CardBudgetInfo,
    ContentKind,
    GeminiReviewResponse,
    QuestionReview,
    UsageInfo,
    review_from_gemini,
)
from anki_bot.pdf_extract import prepare_pdf_question_text
from anki_bot.usage import UsageRecord, usage_from_metadata

DEFAULT_MODEL = AUTO_MODEL
TUTOR_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "tutor.md"
LECTURE_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "lecture.md"

ACCURACY_ADDENDUM = """
## Accuracy over coverage

Prefer accuracy over hitting the card count range. Never invent facts not shown in the source.
Omit unclear facts. One atomic grounded cloze per card. Do not pad to reach the target range.
Fewer excellent cards beats filling the quota.
"""

BULK_QBANK_ADDENDUM = """
## Bulk qbank mode

Keep output compact: at most 3 cloze cards, concise distractors, minimal high_yield rows.
Do not pad output to hit card targets.
"""

_prompt_cache: dict[tuple[str, str], str] = {}


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


def _bulk_mode_enabled() -> bool:
    return os.getenv("ANKI_BOT_BULK_QBANK", "").strip().lower() in {"1", "true", "yes"}


def _escalate_enabled() -> bool:
    return os.getenv("ANKI_BOT_ESCALATE_PRO", "").strip().lower() in {"1", "true", "yes"}


def _cache_prompts_enabled() -> bool:
    return os.getenv("ANKI_BOT_CACHE_PROMPTS", "").strip().lower() in {"1", "true", "yes"}


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


def _maybe_downscale_image(path: Path) -> tuple[bytes, str]:
    mime = _mime_type(path)
    raw_max = os.getenv("ANKI_BOT_MAX_IMAGE_SIDE", "").strip()
    if not raw_max:
        return path.read_bytes(), mime

    max_side = int(raw_max)
    with Image.open(path) as img:
        width, height = img.size
        longest = max(width, height)
        if longest <= max_side:
            return path.read_bytes(), mime

        scale = max_side / longest
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        resized = img.convert("RGB").resize(new_size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        fmt = "PNG" if path.suffix.lower() == ".png" else "JPEG"
        resized.save(buffer, format=fmt, quality=85)
        out_mime = "image/png" if fmt == "PNG" else "image/jpeg"
        return buffer.getvalue(), out_mime


def _image_part(path: Path) -> types.Part:
    data, mime = _maybe_downscale_image(path)
    return types.Part.from_bytes(data=data, mime_type=mime)


def _pdf_part(path: Path) -> types.Part:
    data = path.read_bytes()
    return types.Part.from_bytes(data=data, mime_type="application/pdf")


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return genai.Client(api_key=api_key)


def _resolve_requested(model: str | None) -> str:
    return (model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL).strip()


def _is_auto_model(raw: str) -> bool:
    return raw.lower() in {"", "auto", "default"}


def resolve_model_name(model: str | None = None) -> str:
    """Return configured model id; ``auto`` means router picks Flash vs Pro per item."""
    raw = _resolve_requested(model)
    if _is_auto_model(raw):
        return AUTO_MODEL
    return normalize_model(raw)


def _print_model_choice(choice: ModelChoice) -> None:
    if not choice.auto_selected:
        return
    if choice.reasons:
        print(f"Model {choice.model} (auto: {'; '.join(choice.reasons)})")
    else:
        print(f"Model {choice.model} (auto)")


def _budget_instruction(budget: CardBudget) -> str:
    return (
        f"\n\nTarget cloze cards: {budget.prompt_range()} when enough grounded material exists."
    )


def _question_static_parts(budget: CardBudget) -> list[str]:
    parts: list[str] = [
        load_tutor_prompt(),
        ACCURACY_ADDENDUM,
        _budget_instruction(budget),
    ]
    if _bulk_mode_enabled():
        parts.append(BULK_QBANK_ADDENDUM)
    return parts


def _lecture_static_parts(budget: CardBudget) -> list[str]:
    return [
        load_lecture_prompt(),
        ACCURACY_ADDENDUM,
        _budget_instruction(budget),
    ]


def _get_cached_content_name(
    client: genai.Client,
    model_name: str,
    cache_kind: str,
    static_parts: list[str],
) -> str | None:
    if not _cache_prompts_enabled():
        return None

    key = (normalize_model(model_name), cache_kind)
    if key in _prompt_cache:
        return _prompt_cache[key]

    try:
        cache = client.caches.create(
            model=f"models/{normalize_model(model_name)}",
            config=types.CreateCachedContentConfig(
                contents=[*static_parts, "\n\nReturn JSON matching the schema exactly."],
                ttl="3600s",
            ),
        )
        _prompt_cache[key] = cache.name
        return cache.name
    except (genai_errors.ClientError, AttributeError, TypeError, ValueError):
        return None


def _call_gemini(
    client: genai.Client,
    model_name: str,
    *,
    static_parts: list[str],
    dynamic_parts: list[types.Part | str],
    cache_kind: str,
) -> tuple[GeminiReviewResponse, UsageRecord | None]:
    schema = GeminiReviewResponse.model_json_schema()
    model_name = normalize_model(model_name)

    cached_name = _get_cached_content_name(client, model_name, cache_kind, static_parts)
    contents: list[types.Part | str] = (
        dynamic_parts if cached_name else [*static_parts, *dynamic_parts]
    )

    config = types.GenerateContentConfig(
        temperature=0.1,
        response_mime_type="application/json",
        response_schema=schema,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True,
        ),
    )
    if cached_name:
        config.cached_content = cached_name

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
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
                f"Try {FLASH_MODEL!r} or {PRO_MODEL!r}."
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


def _should_escalate_to_pro(parsed: GeminiReviewResponse) -> bool:
    if not _escalate_enabled():
        return False
    if parsed.item.confidence < 0.85:
        return True
    for warning in parsed.warnings:
        lowered = warning.lower()
        if "missing explanation" in lowered or "ambiguous correct" in lowered:
            return True
    return False


def _pick_question_model(
    *,
    pdf_paths: list[Path],
    image_paths: list[Path],
    model: str | None,
) -> ModelChoice:
    raw = _resolve_requested(model)
    if not _is_auto_model(raw):
        return ModelChoice(model=normalize_model(raw), reasons=(), auto_selected=False)
    return choose_model_for_question(pdf_paths=pdf_paths, image_paths=image_paths, requested=AUTO_MODEL)


def _pick_lecture_model(
    *,
    text_length: int,
    html_paths: list[Path],
    model: str | None,
) -> ModelChoice:
    raw = _resolve_requested(model)
    if not _is_auto_model(raw):
        return ModelChoice(model=normalize_model(raw), reasons=(), auto_selected=False)
    return choose_model_for_lecture(text_length, html_paths, requested=AUTO_MODEL)


def _run_question_gemini(
    client: genai.Client,
    *,
    model_name: str,
    card_budget: CardBudget,
    pdfs: list[Path],
    images: list[Path],
    force_vision: bool = False,
) -> tuple[GeminiReviewResponse, UsageRecord | None, list[str]]:
    extra_warnings: list[str] = []
    dynamic: list[types.Part | str] = [
        "\n\nAnalyze this board-style question. Return JSON matching the schema exactly.",
    ]

    use_vision_pdfs = force_vision
    if pdfs and not force_vision:
        pdf_result = prepare_pdf_question_text(pdfs)
        extra_warnings.extend(pdf_result.warnings)
        if pdf_result.used_vision:
            use_vision_pdfs = True
        else:
            dynamic.append(
                f"\n\n--- QUESTION TEXT (extracted from PDF) ---\n{pdf_result.text}\n--- END QUESTION TEXT ---"
            )

    if use_vision_pdfs:
        for path in pdfs:
            dynamic.append(_pdf_part(path))

    for path in images:
        dynamic.append(_image_part(path))

    parsed, usage = _call_gemini(
        client,
        model_name,
        static_parts=_question_static_parts(card_budget),
        dynamic_parts=dynamic,
        cache_kind="question",
    )
    return parsed, usage, extra_warnings


def review_question(
    question_id: str,
    *,
    pdf_paths: list[Path] | None = None,
    image_paths: list[Path] | None = None,
    model: str | None = None,
    budget: CardBudget | None = None,
    track: str = "",
    client: genai.Client | None = None,
) -> QuestionReview:
    """Send PDF and/or screenshot sources to Gemini and return structured review."""
    pdfs = pdf_paths or []
    images = image_paths or []
    if not pdfs and not images:
        raise ValueError("No PDF or image sources provided")

    from anki_bot.card_budget import budget_for_question

    client = client or get_client()
    choice = _pick_question_model(pdf_paths=pdfs, image_paths=images, model=model)
    _print_model_choice(choice)
    model_name = choice.model
    card_budget = budget or budget_for_question()

    parsed, usage, extra_warnings = _run_question_gemini(
        client,
        model_name=model_name,
        card_budget=card_budget,
        pdfs=pdfs,
        images=images,
    )

    if _should_escalate_to_pro(parsed) and model_name != PRO_MODEL:
        print(f"Escalating {question_id} to {PRO_MODEL} (low confidence or missing explanation)")
        parsed, usage, escalate_warnings = _run_question_gemini(
            client,
            model_name=PRO_MODEL,
            card_budget=card_budget,
            pdfs=pdfs,
            images=images,
            force_vision=True,
        )
        extra_warnings.extend(escalate_warnings)
        model_name = PRO_MODEL

    review = review_from_gemini(
        question_id,
        parsed,
        kind=ContentKind.QUESTION,
        source_images=[str(p.resolve()) for p in images],
        source_pdfs=[str(p.resolve()) for p in pdfs],
    )
    review.warnings.extend(extra_warnings)
    return _attach_metadata(
        review,
        budget=card_budget,
        usage=usage,
        model_name=model_name,
        track=track,
    )


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
    return review_question(
        question_id,
        image_paths=image_paths,
        model=model,
        budget=budget,
        track=track,
        client=client,
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
    lecture_text, extract_warnings, meta = combine_lecture_html(
        html_paths,
        group_id=lecture_id,
    )
    if not lecture_text.strip():
        raise RuntimeError(
            f"No extractable text in HTML file(s): {', '.join(p.name for p in html_paths)}"
        )

    choice = _pick_lecture_model(
        text_length=len(lecture_text),
        html_paths=html_paths,
        model=model,
    )
    _print_model_choice(choice)
    model_name = choice.model

    if budget is None:
        card_budget, budget_warnings = budget_for_lecture(
            lecture_hours=meta.hours,
            char_count=len(lecture_text),
        )
        review_warnings = budget_warnings
    else:
        card_budget = budget
        review_warnings = []

    dynamic: list[types.Part | str] = [
        "\n\nAnalyze this lecture text extracted from HTML. Return JSON matching the schema exactly.",
        f"\n\n--- LECTURE TEXT ---\n{lecture_text}\n--- END LECTURE TEXT ---",
    ]

    parsed, usage = _call_gemini(
        client,
        model_name,
        static_parts=_lecture_static_parts(card_budget),
        dynamic_parts=dynamic,
        cache_kind="lecture",
    )
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
    return review_question(
        group.id,
        pdf_paths=list(group.pdf_paths),
        image_paths=list(group.image_paths),
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
        source_pdfs = [str(p.resolve()) for p in group.pdf_paths]
        review = review_from_gemini(
            group.id,
            parsed,
            kind=group.kind,
            source_images=source_images,
            source_html=source_html,
            source_pdfs=source_pdfs,
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
        model_name=PRO_MODEL,
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
