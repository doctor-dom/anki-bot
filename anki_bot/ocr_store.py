"""Persist raw PNG OCR text alongside review JSON for later edits."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from anki_bot.image_ocr import PngPrepareResult
from anki_bot.outputs import track_output_root

OCR_DIRNAME = "ocr"


def ocr_dir(output_root: Path, track: str) -> Path:
    return track_output_root(output_root, track) / OCR_DIRNAME


def ocr_paths(output_root: Path, track: str, review_id: str) -> tuple[Path, Path]:
    base = ocr_dir(output_root, track) / review_id
    return base.with_suffix(".txt"), base.with_suffix(".json")


def write_png_ocr_artifact(
    output_root: Path,
    track: str,
    review_id: str,
    png_result: PngPrepareResult,
    *,
    source_images: list[str],
) -> str:
    """Write ``.txt`` (raw text) and ``.json`` (metadata). Returns track-relative path."""
    txt_path, json_path = ocr_paths(output_root, track, review_id)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(png_result.text, encoding="utf-8")

    payload = {
        "id": review_id,
        "track": track,
        "saved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "text": png_result.text,
        "used_ocr": png_result.used_ocr,
        "used_vision": png_result.used_vision,
        "vision_paths": [str(p) for p in png_result.vision_paths],
        "source_images": source_images,
        "warnings": list(png_result.warnings),
    }
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return f"{OCR_DIRNAME}/{review_id}.json"


def read_png_ocr_text(output_root: Path, track: str, review_id: str) -> str | None:
    txt_path, json_path = ocr_paths(output_root, track, review_id)
    if txt_path.is_file():
        return txt_path.read_text(encoding="utf-8")
    if json_path.is_file():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        text = data.get("text")
        return text if isinstance(text, str) else None
    return None
