"""Command-line interface for anki-bot."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from anki_bot.gemini_review import DEFAULT_MODEL
from anki_bot.pipeline import build_from_reviews, process_path, reviews_dir


def _default_output() -> Path:
    return Path("output")


def _optional_max_cards(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    return int(raw)


def cmd_process(args: argparse.Namespace) -> int:
    load_dotenv()
    input_path = Path(args.input).resolve()
    output_root = Path(args.output).resolve()
    fixture = Path(args.fixture).resolve() if args.fixture else None

    try:
        reviews = process_path(
            input_path,
            output_root,
            review_only=args.review_only,
            model=args.model,
            max_cards=args.max_cards,
            deck_name=args.deck,
            fixture=fixture,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Processed {len(reviews)} item(s).")
    print(f"Reviews: {reviews_dir(output_root)}")
    return 0


def cmd_build_apkg(args: argparse.Namespace) -> int:
    load_dotenv()
    reviews_path = Path(args.reviews).resolve()
    output_root = Path(args.output).resolve()

    if not reviews_path.is_dir():
        print(f"Error: reviews directory not found: {reviews_path}", file=sys.stderr)
        return 1

    reviews, count = build_from_reviews(
        reviews_path,
        output_root,
        deck_name=args.deck,
        max_cards=args.max_cards,
    )
    print(f"Rebuilt from {len(reviews)} review file(s), {count} note(s) across labeled packs.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anki-bot",
        description="Screenshot question review → high-yield HTML + Anki cloze .apkg",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    process = sub.add_parser("process", help="Process screenshot(s) with Gemini")
    process.add_argument("input", help="Folder of screenshots or a single image")
    process.add_argument(
        "-o",
        "--output",
        default=str(_default_output()),
        help="Output directory (default: output/)",
    )
    process.add_argument(
        "--review-only",
        action="store_true",
        help="Write JSON/HTML only; skip .apkg",
    )
    process.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        help=f"Gemini model override (default: {DEFAULT_MODEL})",
    )
    process.add_argument(
        "--max-cards",
        type=int,
        default=_optional_max_cards(os.getenv("ANKI_BOT_MAX_CARDS")),
        help="Optional hard cap on cloze cards (default: adaptive by kind/duration)",
    )
    process.add_argument(
        "--deck",
        default=os.getenv("ANKI_BOT_DECK", "HUB::anki-bot"),
        help="Legacy deck override (labeled packs use topic/qbank names)",
    )
    process.add_argument(
        "--fixture",
        help="Use a JSON fixture instead of calling Gemini (for testing)",
    )
    process.set_defaults(func=cmd_process)

    build = sub.add_parser(
        "build-apkg",
        help="Rebuild high-yield.html and .apkg from edited review JSON",
    )
    build.add_argument(
        "reviews",
        nargs="?",
        default="output/reviews",
        help="Path to reviews folder (default: output/reviews)",
    )
    build.add_argument(
        "-o",
        "--output",
        default=str(_default_output()),
        help="Output directory (default: output/)",
    )
    build.add_argument(
        "--max-cards",
        type=int,
        default=_optional_max_cards(os.getenv("ANKI_BOT_MAX_CARDS")),
        help="Optional hard cap on cloze cards (default: use stored budget)",
    )
    build.add_argument("--deck", default=os.getenv("ANKI_BOT_DECK", "HUB::anki-bot"))
    build.set_defaults(func=cmd_build_apkg)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
