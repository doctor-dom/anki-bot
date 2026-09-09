"""Gemini vision API: extract grounded review JSON from screenshots."""

from __future__ import annotations

import json
import os
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import ValidationError

from anki_bot.model_select import FLASH_MODEL, PRO_MODEL, ModelChoice, choose_model
from anki_bot.models import GeminiReviewResponse, QuestionReview, review_from_gemini

DEFAULT_MODEL = FLASH_MODEL
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "tutor.md"


def load_tutor_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "Extract grounded teaching points from the screenshots only."


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


def resolve_model(image_paths: list[Path], model: str | None = None) -> ModelChoice:
    return choose_model(image_paths, requested=model)


def review_images(
    question_id: str,
    image_paths: list[Path],
    *,
    model: str | None = None,
    client: genai.Client | None = None,
) -> QuestionReview:
    """Send screenshots to Gemini and return structured review."""
    if not image_paths:
        raise ValueError("No images provided")

    client = client or get_client()
    choice = resolve_model(image_paths, model)
    model_name = choice.model
    if choice.auto_selected:
        reason = "; ".join(choice.reasons) if choice.reasons else "simple screenshot set"
        print(f"[{question_id}] Auto model: {model_name} ({reason})")
    prompt = load_tutor_prompt()

    parts: list[types.Part | str] = [
        prompt,
        "\n\nAnalyze these question screenshot(s). Return JSON matching the schema exactly.",
    ]
    for path in image_paths:
        parts.append(_image_part(path))

    schema = GeminiReviewResponse.model_json_schema()

    response = client.models.generate_content(
        model=model_name,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )

    raw = response.text or ""
    try:
        payload = json.loads(raw)
        parsed = GeminiReviewResponse.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError(f"Gemini returned invalid JSON: {exc}\nRaw: {raw[:500]}") from exc

    source_images = [str(p.resolve()) for p in image_paths]
    review = review_from_gemini(question_id, parsed, source_images)

    if choice.auto_selected:
        if choice.model == PRO_MODEL and choice.reasons:
            detail = "; ".join(choice.reasons)
            review.warnings.insert(0, f"Auto-selected {PRO_MODEL}: {detail}")
        else:
            review.warnings.insert(0, f"Auto-selected {FLASH_MODEL} (simple screenshot set)")

    return review


def review_images_from_fixture(
    question_id: str,
    image_paths: list[Path],
    fixture_path: Path,
) -> QuestionReview:
    """Load review from a JSON fixture (for tests / offline use)."""
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if "item" in payload and "id" in payload:
        return QuestionReview.model_validate(payload)
    parsed = GeminiReviewResponse.model_validate(payload)
    source_images = [str(p.resolve()) for p in image_paths]
    return review_from_gemini(question_id, parsed, source_images)
