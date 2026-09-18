"""Extract plain text from selectable PDF qbanks."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

MIN_MCQ_TEXT_CHARS = 200


class PdfInputMode(str, Enum):
    AUTO = "auto"
    TEXT = "text"
    VISION = "vision"


@dataclass(frozen=True)
class PdfTextResult:
    text: str
    used_vision: bool
    warnings: tuple[str, ...] = ()


def pdf_input_mode() -> PdfInputMode:
    raw = os.getenv("ANKI_BOT_PDF_MODE", "auto").strip().lower()
    try:
        return PdfInputMode(raw)
    except ValueError:
        return PdfInputMode.AUTO


def extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        chunk = page.extract_text() or ""
        if chunk.strip():
            parts.append(chunk)
    return "\n\n".join(parts).strip()


def _looks_like_mcq(text: str) -> bool:
    if len(text) < MIN_MCQ_TEXT_CHARS:
        return False
    upper = text.upper()
    if "CORRECT" in upper or "EXPLANATION" in upper:
        return True
    if re.search(r"\b[A-E][\).\]]\s", text):
        return True
    if re.search(r"\(\s*[A-E]\s*\)", text):
        return True
    return False


def prepare_pdf_question_text(
    pdf_paths: list[Path],
    *,
    mode: PdfInputMode | None = None,
) -> PdfTextResult:
    """Return combined extracted text, or signal vision fallback."""
    mode = mode or pdf_input_mode()
    if mode == PdfInputMode.VISION:
        return PdfTextResult(text="", used_vision=True, warnings=("ANKI_BOT_PDF_MODE=vision",))

    if not pdf_paths:
        return PdfTextResult(text="", used_vision=True)

    sections: list[str] = []
    warnings: list[str] = []
    for path in pdf_paths:
        try:
            text = extract_pdf_text(path)
        except Exception as exc:  # noqa: BLE001 - surface as vision fallback
            warnings.append(f"PDF text extract failed for {path.name}: {exc}")
            if mode == PdfInputMode.TEXT:
                raise RuntimeError(f"Could not extract text from {path}") from exc
            return PdfTextResult(
                text="",
                used_vision=True,
                warnings=tuple(warnings),
            )
        if not text.strip():
            warnings.append(f"No extractable text in {path.name}")
            if mode == PdfInputMode.TEXT:
                raise RuntimeError(f"No extractable text in {path}")
            return PdfTextResult(text="", used_vision=True, warnings=tuple(warnings))
        sections.append(f"=== {path.name} ===\n{text}")

    combined = "\n\n".join(sections).strip()
    if mode == PdfInputMode.TEXT:
        return PdfTextResult(text=combined, used_vision=False, warnings=tuple(warnings))

    if _looks_like_mcq(combined):
        return PdfTextResult(text=combined, used_vision=False, warnings=tuple(warnings))

    warnings.append("Extracted PDF text does not look like a full MCQ; using vision PDF")
    return PdfTextResult(text="", used_vision=True, warnings=tuple(warnings))
