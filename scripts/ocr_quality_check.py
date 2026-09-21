#!/usr/bin/env python3
"""Calibrate Tesseract OCR on local qbank PNGs under output/ (no Gemini calls)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from anki_bot.image_ocr import (  # noqa: E402
    prepare_png_question_input,
    recovered_choice_letters,
    tesseract_available,
)
from anki_bot.models import QuestionReview
from anki_bot.outputs import iter_review_json_paths
from anki_bot.pdf_extract import looks_like_mcq

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _discover_image_paths(output_root: Path) -> list[Path]:
    found: list[Path] = []
    for path in output_root.rglob("*"):
        if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file():
            found.append(path.resolve())

    for review_path in iter_review_json_paths(output_root):
        try:
            review = QuestionReview.model_validate(
                json.loads(review_path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, ValueError):
            continue
        for raw in review.source_images:
            p = Path(raw)
            if p.is_file():
                found.append(p.resolve())

    unique = sorted({p for p in found}, key=lambda p: str(p).lower())
    return unique


def _gold_choices(review: QuestionReview | None) -> set[str]:
    if review is None:
        return set()
    letters = {c.letter.strip().upper() for c in review.item.choices if c.letter}
    if review.item.correct_letter:
        letters.add(review.item.correct_letter.strip().upper())
    return {letter for letter in letters if letter in {"A", "B", "C", "D", "E"}}


def _review_for_image(output_root: Path, image_path: Path) -> QuestionReview | None:
    target = str(image_path.resolve())
    for review_path in iter_review_json_paths(output_root):
        try:
            review = QuestionReview.model_validate(
                json.loads(review_path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, ValueError):
            continue
        if any(str(Path(p).resolve()) == target for p in review.source_images):
            return review
    return None


def _route_label(result) -> str:
    if result.text and not result.vision_paths:
        return "text"
    if result.text and result.vision_paths:
        return "hybrid"
    return "vision"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_root",
        nargs="?",
        default="output",
        type=Path,
        help="Path to output/ (default: ./output)",
    )
    args = parser.parse_args()
    output_root = args.output_root.resolve()

    if not tesseract_available():
        print("Tesseract not found on PATH. Install before running calibration.")
        return 1

    images = _discover_image_paths(output_root)
    if not images:
        print(f"No PNG/JPG files under {output_root} and no source_images in review JSON.")
        return 1

    print(f"Found {len(images)} image(s). Running local OCR (no Gemini).\n")

    by_group: dict[str, list[Path]] = defaultdict(list)
    for path in images:
        by_group[path.parent.name].append(path)

    total_pages = 0
    text_routes = 0
    hybrid_routes = 0
    vision_routes = 0
    choice_hits = 0
    choice_total = 0
    missing_explanation = 0

    for path in images:
        total_pages += 1
        try:
            text = __import__("anki_bot.image_ocr", fromlist=["ocr_image_text"]).ocr_image_text(
                path
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{path.name}: OCR error -> vision ({exc})")
            vision_routes += 1
            continue

        prep = prepare_png_question_input([path])
        route = _route_label(prep)
        if route == "text":
            text_routes += 1
        elif route == "hybrid":
            hybrid_routes += 1
        else:
            vision_routes += 1

        ocr_choices = recovered_choice_letters(text)
        review = _review_for_image(output_root, path)
        gold = _gold_choices(review)
        if gold:
            choice_total += 1
            if gold & ocr_choices:
                choice_hits += 1

        upper = text.upper()
        if review and ("EXPLANATION" in (review.correct_pearl or "").upper() or review.item.correct_text):
            if "EXPLANATION" not in upper and "CORRECT" not in upper:
                missing_explanation += 1

        mcq = looks_like_mcq(text)
        print(
            f"{path.name}: {len(text)} chars, mcq={mcq}, choices={sorted(ocr_choices) or '-'}, "
            f"route={route}"
        )

    vision_avoided_pct = (
        100.0 * (text_routes + hybrid_routes) / total_pages if total_pages else 0.0
    )
    choice_recall = (100.0 * choice_hits / choice_total) if choice_total else 0.0

    print("\n--- Summary ---")
    print(f"Pages: {total_pages}")
    print(f"Routes: text={text_routes}, hybrid={hybrid_routes}, vision={vision_routes}")
    print(f"Vision avoided (text+hybrid): {vision_avoided_pct:.0f}%")
    print(f"Choice-letter recall (vs review JSON): {choice_recall:.0f}% ({choice_hits}/{choice_total})")
    print(f"Pages missing Correct/Explanation in OCR (with gold review): {missing_explanation}")
    print(f"Question folders/groups touched: {len(by_group)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
