"""Local OCR for qbank PNG screenshots (Tesseract), mirroring PDF text extract."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageStat

from anki_bot.pdf_extract import looks_like_mcq

MIN_OCR_CHARS_FOR_PAGE = 80
FIGURE_NAME_PATTERN = re.compile(
    r"(cxr|x-?ray|ecg|ekg|rash|figure|fig-|image|photo|scan|histology|microscopy|"
    r"derm|pathology|graph|chart|diagram)",
    re.IGNORECASE,
)


class PngInputMode(str, Enum):
    AUTO = "auto"
    TEXT = "text"
    VISION = "vision"


@dataclass(frozen=True)
class PngPrepareResult:
    text: str
    used_vision: bool
    vision_paths: tuple[Path, ...]
    used_ocr: bool
    warnings: tuple[str, ...] = ()


_tesseract_missing_warned = False
_tesseract_configured = False

_WINDOWS_TESSERACT_CANDIDATES = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def _resolve_tesseract_cmd() -> Path | None:
    raw = os.getenv("ANKI_BOT_TESSERACT_CMD", "").strip()
    if raw:
        path = Path(raw)
        return path if path.is_file() else None
    for candidate in _WINDOWS_TESSERACT_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def configure_tesseract() -> bool:
    """Point pytesseract at tesseract.exe (PATH, env, or common Windows install)."""
    global _tesseract_configured
    try:
        import pytesseract
    except ImportError:
        return False

    if _tesseract_configured:
        return True

    resolved = _resolve_tesseract_cmd()
    if resolved is not None:
        pytesseract.pytesseract.tesseract_cmd = str(resolved)

    _tesseract_configured = True
    return True


def png_keep_ocr_text() -> bool:
    return os.getenv("ANKI_BOT_PNG_KEEP_OCR", "").strip().lower() in {"1", "true", "yes"}


def png_input_mode() -> PngInputMode:
    raw = os.getenv("ANKI_BOT_PNG_MODE", "auto").strip().lower()
    try:
        return PngInputMode(raw)
    except ValueError:
        return PngInputMode.AUTO


def tesseract_available() -> bool:
    if not configure_tesseract():
        return False
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except (ImportError, OSError, RuntimeError):
        return False


def _warn_tesseract_missing_once() -> None:
    global _tesseract_missing_warned
    if _tesseract_missing_warned:
        return
    _tesseract_missing_warned = True
    print(
        "Tesseract OCR not available; PNG review will use Gemini vision. "
        "Install: winget install UB-Mannheim.TesseractOCR (Windows) or apt install tesseract-ocr. "
        "If already installed, add Tesseract to PATH or set ANKI_BOT_TESSERACT_CMD."
    )


def _preprocess_for_ocr(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    width, height = gray.size
    longest = max(width, height)
    if longest < 1200:
        scale = 1200 / longest
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        gray = gray.resize(new_size, Image.Resampling.LANCZOS)
    gray = ImageEnhance.Contrast(gray).enhance(1.4)
    gray = gray.filter(ImageFilter.SHARPEN)
    return gray


def ocr_image_text(path: Path) -> str:
    if not configure_tesseract():
        raise RuntimeError("pytesseract is not installed")
    import pytesseract

    with Image.open(path) as img:
        prepared = _preprocess_for_ocr(img)
        return pytesseract.image_to_string(prepared).strip()


def _filename_suggests_figure(path: Path) -> bool:
    return bool(FIGURE_NAME_PATTERN.search(path.stem))


def path_is_figure(path: Path) -> bool:
    """True when a screenshot should stay on the vision path (diagram / photo)."""
    return _image_looks_like_figure(path)


def _image_looks_like_figure(path: Path) -> bool:
    if _filename_suggests_figure(path):
        return True
    color_threshold = float(os.getenv("ANKI_BOT_FIGURE_COLOR_VARIANCE", "55"))
    try:
        with Image.open(path) as img:
            rgb = img.convert("RGB")
            color_variance = sum(ImageStat.Stat(rgb).stddev) / 3.0
            return color_variance >= color_threshold
    except OSError:
        return False


def _page_sparse_ocr(text: str) -> bool:
    return len(text.strip()) < MIN_OCR_CHARS_FOR_PAGE


def recovered_choice_letters(text: str) -> set[str]:
    found: set[str] = set()
    for match in re.finditer(r"\b([A-E])[\).\]]\s", text):
        found.add(match.group(1))
    for match in re.finditer(r"\(\s*([A-E])\s*\)", text):
        found.add(match.group(1))
    return found


def prepare_png_question_input(
    image_paths: list[Path],
    *,
    mode: PngInputMode | None = None,
    force_vision: bool = False,
) -> PngPrepareResult:
    """OCR screenshots to text, optionally keeping figure pages as vision."""
    mode = mode or png_input_mode()
    if force_vision or mode == PngInputMode.VISION:
        return PngPrepareResult(
            text="",
            used_vision=True,
            vision_paths=tuple(image_paths),
            used_ocr=False,
            warnings=(
                ("ANKI_BOT_PNG_MODE=vision",)
                if mode == PngInputMode.VISION
                else ("force_vision",)
            ),
        )

    if not image_paths:
        return PngPrepareResult(
            text="",
            used_vision=True,
            vision_paths=(),
            used_ocr=False,
        )

    if not tesseract_available():
        _warn_tesseract_missing_once()
        if mode == PngInputMode.TEXT:
            raise RuntimeError(
                "Tesseract is required for ANKI_BOT_PNG_MODE=text but was not found on PATH."
            )
        return PngPrepareResult(
            text="",
            used_vision=True,
            vision_paths=tuple(image_paths),
            used_ocr=False,
            warnings=("Tesseract not installed; using vision PNG",),
        )

    sections: list[str] = []
    vision_paths: list[Path] = []
    warnings: list[str] = []

    for path in image_paths:
        try:
            page_text = ocr_image_text(path)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"OCR failed for {path.name}: {exc}")
            if mode == PngInputMode.TEXT:
                raise RuntimeError(f"Could not OCR {path}") from exc
            vision_paths.append(path)
            continue

        keep_as_figure = _image_looks_like_figure(path) and (
            _page_sparse_ocr(page_text) or _filename_suggests_figure(path)
        )
        if keep_as_figure:
            vision_paths.append(path)
            if page_text.strip():
                sections.append(f"=== {path.name} (OCR partial) ===\n{page_text}")
            warnings.append(f"Keeping {path.name} as vision (figure-like)")
            continue

        if _page_sparse_ocr(page_text):
            warnings.append(f"Sparse OCR for {path.name}; using vision for that page")
            vision_paths.append(path)
            continue

        sections.append(f"=== {path.name} ===\n{page_text}")

    combined = "\n\n".join(sections).strip()

    if mode == PngInputMode.TEXT:
        if not combined:
            raise RuntimeError("No OCR text extracted from PNG(s)")
        return PngPrepareResult(
            text=combined,
            used_vision=bool(vision_paths),
            vision_paths=tuple(vision_paths),
            used_ocr=True,
            warnings=tuple(warnings),
        )

    if not combined:
        warnings.append("No usable OCR text; using vision PNG")
        return PngPrepareResult(
            text="",
            used_vision=True,
            vision_paths=tuple(image_paths),
            used_ocr=False,
            warnings=tuple(warnings),
        )

    if not looks_like_mcq(combined):
        if png_keep_ocr_text():
            warnings.append("OCR text kept (ANKI_BOT_PNG_KEEP_OCR); vision only for figure pages")
            return PngPrepareResult(
                text=combined,
                used_vision=bool(vision_paths),
                vision_paths=tuple(vision_paths),
                used_ocr=True,
                warnings=tuple(warnings),
            )
        warnings.append("OCR text does not look like a full MCQ; using vision PNG")
        return PngPrepareResult(
            text="",
            used_vision=True,
            vision_paths=tuple(image_paths),
            used_ocr=True,
            warnings=tuple(warnings),
        )

    return PngPrepareResult(
        text=combined,
        used_vision=bool(vision_paths),
        vision_paths=tuple(vision_paths),
        used_ocr=True,
        warnings=tuple(warnings),
    )
