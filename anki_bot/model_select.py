"""Choose Gemini Flash vs Pro from screenshot complexity heuristics."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-2.5-pro"
AUTO_MODEL = "auto"


@dataclass(frozen=True)
class ImageSignals:
    path: Path
    width: int
    height: int
    pixels: int
    file_size: int
    edge_score: float
    color_variance: float


@dataclass(frozen=True)
class ModelChoice:
    model: str
    reasons: tuple[str, ...]
    auto_selected: bool


def _analyze_image(path: Path) -> ImageSignals:
    with Image.open(path) as img:
        width, height = img.size
        gray = img.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_score = ImageStat.Stat(edges).mean[0]
        rgb = img.convert("RGB")
        color_variance = sum(ImageStat.Stat(rgb).stddev) / 3.0
        return ImageSignals(
            path=path,
            width=width,
            height=height,
            pixels=width * height,
            file_size=path.stat().st_size,
            edge_score=edge_score,
            color_variance=color_variance,
        )


def _threshold(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def assess_images(image_paths: list[Path]) -> tuple[int, list[str]]:
    """Return complexity score and human-readable reasons."""
    if not image_paths:
        return 0, []

    signals = [_analyze_image(p) for p in image_paths]
    score = 0
    reasons: list[str] = []

    image_count_threshold = int(os.getenv("ANKI_BOT_PRO_MIN_IMAGES", "3"))
    if len(signals) >= image_count_threshold:
        score += 2
        reasons.append(f"{len(signals)} screenshots (multi-page item)")

    max_side_threshold = int(os.getenv("ANKI_BOT_PRO_MAX_SIDE", "1800"))
    megapixel_threshold = float(os.getenv("ANKI_BOT_PRO_MEGAPIXELS", "1.8"))
    file_kb_threshold = float(os.getenv("ANKI_BOT_PRO_FILE_KB", "800"))
    edge_threshold = _threshold("ANKI_BOT_PRO_EDGE_SCORE", 28.0)
    color_threshold = _threshold("ANKI_BOT_PRO_COLOR_VARIANCE", 50.0)
    score_threshold = int(os.getenv("ANKI_BOT_PRO_SCORE", "2"))

    for sig in signals:
        longest = max(sig.width, sig.height)
        megapixels = sig.pixels / 1_000_000
        file_kb = sig.file_size / 1024

        if longest >= max_side_threshold:
            score += 1
            reasons.append(f"high-res image {sig.path.name} ({sig.width}x{sig.height})")
        if megapixels >= megapixel_threshold:
            score += 1
            reasons.append(f"large image {sig.path.name} ({megapixels:.1f} MP)")
        if file_kb >= file_kb_threshold:
            score += 1
            reasons.append(f"heavy screenshot {sig.path.name} ({file_kb:.0f} KB)")
        if sig.edge_score >= edge_threshold:
            score += 1
            reasons.append(
                f"dense layout or chart-like image {sig.path.name} "
                f"(edge score {sig.edge_score:.1f})"
            )
        if sig.color_variance >= color_threshold:
            score += 1
            reasons.append(
                f"color-rich diagram {sig.path.name} "
                f"(color variance {sig.color_variance:.1f})"
            )

    # Deduplicate reasons while preserving order
    seen: set[str] = set()
    unique_reasons: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            unique_reasons.append(reason)

    return score, unique_reasons


def choose_model(
    image_paths: list[Path],
    *,
    requested: str | None = None,
) -> ModelChoice:
    """Resolve model: explicit override, env, or auto from image complexity."""
    env_model = (requested or os.getenv("GEMINI_MODEL") or AUTO_MODEL).strip().lower()

    if env_model in {FLASH_MODEL, "flash"}:
        return ModelChoice(model=FLASH_MODEL, reasons=(), auto_selected=False)
    if env_model in {PRO_MODEL, "pro"}:
        return ModelChoice(model=PRO_MODEL, reasons=(), auto_selected=False)
    if env_model not in {AUTO_MODEL, ""}:
        # User supplied a full model id (e.g. gemini-2.5-flash-lite)
        return ModelChoice(model=env_model, reasons=(), auto_selected=False)

    score, reasons = assess_images(image_paths)
    score_threshold = int(os.getenv("ANKI_BOT_PRO_SCORE", "2"))
    if score >= score_threshold:
        return ModelChoice(model=PRO_MODEL, reasons=tuple(reasons), auto_selected=True)

    return ModelChoice(
        model=FLASH_MODEL,
        reasons=("simple screenshot set",) if not reasons else (f"score {score} < {score_threshold}",),
        auto_selected=True,
    )
