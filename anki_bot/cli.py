"""Command-line interface for anki-bot."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from anki_bot.gemini_review import DEFAULT_MODEL
from anki_bot.paths import DEFAULT_OUTPUT_DIRNAME, resolve_default_input, resolve_output_root
from anki_bot.estimate import estimate_path, format_estimate_report
from anki_bot.drive_sync import (
    default_rclone_pull_output,
    default_rclone_push_input,
    default_rclone_push_output,
    rclone_available,
    rclone_copy,
)
from anki_bot.paths import find_repo_root
from anki_bot.pipeline import build_from_reviews, process_path, reviews_dir


def _default_output() -> Path:
    return Path(DEFAULT_OUTPUT_DIRNAME)


def _optional_max_cards(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    return int(raw)


def _resolve_input_path(raw: str | None) -> Path:
    if raw is None or raw == "":
        return resolve_default_input()
    return Path(raw).resolve()


def cmd_process(args: argparse.Namespace) -> int:
    load_dotenv()
    input_path = _resolve_input_path(args.input)
    output_root = resolve_output_root(args.output, anchor_path=input_path)
    print(f"Output directory: {output_root}")
    fixture = Path(args.fixture).resolve() if args.fixture else None

    try:
        if getattr(args, "dry_run", False):
            report = estimate_path(input_path, output_root, force=args.force)
            print(format_estimate_report(report))
            return 0

        reviews = process_path(
            input_path,
            output_root,
            review_only=args.review_only,
            model=args.model,
            max_cards=args.max_cards,
            deck_name=args.deck,
            fixture=fixture,
            force=args.force,
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
    output_root = resolve_output_root(args.output, anchor_path=reviews_path)
    print(f"Output directory: {output_root}")

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
        description="Qbank PDFs, screenshots, and lecture HTML → high-yield HTML + Anki cloze .apkg",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def _add_process_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "-o",
            "--output",
            default=str(_default_output()),
            help="Output directory (default: output/)",
        )
        p.add_argument(
            "--review-only",
            action="store_true",
            help="Write JSON/HTML only; skip .apkg",
        )
        p.add_argument(
            "--model",
            default=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
            help=f"Gemini model override (default: {DEFAULT_MODEL})",
        )
        p.add_argument(
            "--max-cards",
            type=int,
            default=_optional_max_cards(os.getenv("ANKI_BOT_MAX_CARDS")),
            help="Optional hard cap on cloze cards (default: adaptive by kind/duration)",
        )
        p.add_argument(
            "--deck",
            default=os.getenv("ANKI_BOT_DECK", "HUB::anki-bot"),
            help="Legacy deck override (labeled packs use topic/qbank names)",
        )
        p.add_argument(
            "--fixture",
            help="Use a JSON fixture instead of calling Gemini (for testing)",
        )
        p.add_argument(
            "--force",
            action="store_true",
            help="Reprocess all discovered groups even if source files are unchanged",
        )
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Estimate API cost and skip/ run counts without calling Gemini",
        )

    process = sub.add_parser(
        "process",
        help="Process PDF qbanks, screenshots, or lecture HTML with Gemini",
    )
    process.add_argument(
        "input",
        nargs="?",
        default=None,
        help="File or folder (default: repo input/)",
    )
    _add_process_flags(process)
    process.set_defaults(func=cmd_process)

    run = sub.add_parser(
        "run",
        help="Process all new/changed content under repo input/ → output/",
    )
    _add_process_flags(run)
    run.set_defaults(func=cmd_process, input=None)

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

    estimate = sub.add_parser(
        "estimate",
        help="Estimate Gemini spend for new/changed items under input/",
    )
    estimate.add_argument(
        "input",
        nargs="?",
        default=None,
        help="File or folder (default: repo input/)",
    )
    estimate.add_argument(
        "-o",
        "--output",
        default=str(_default_output()),
        help="Output directory (default: output/)",
    )
    estimate.add_argument(
        "--force",
        action="store_true",
        help="Treat all groups as would-run (ignore skip fingerprints)",
    )
    estimate.set_defaults(func=cmd_estimate)

    pull = sub.add_parser("pull", help="Copy Google Drive anki-bot/output to local output/")
    pull.set_defaults(func=cmd_pull)

    push_in = sub.add_parser(
        "push-input",
        help="Copy local input/ to Google Drive anki-bot/input",
    )
    push_in.set_defaults(func=cmd_push_input)

    push_out = sub.add_parser(
        "push-output",
        help="Copy local output/ to Google Drive (upload review edits before nightly run)",
    )
    push_out.set_defaults(func=cmd_push_output)

    return parser


def _repo_root() -> Path:
    repo = find_repo_root(Path.cwd())
    return repo if repo is not None else Path.cwd()


def _require_rclone() -> bool:
    if rclone_available():
        return True
    print(
        "Error: rclone not found on PATH. Install from https://rclone.org/downloads/ "
        "or use .\\scripts\\drive-sync.ps1",
        file=sys.stderr,
    )
    return False


def cmd_pull(args: argparse.Namespace) -> int:  # noqa: ARG001
    if not _require_rclone():
        return 1
    root = _repo_root()
    output = root / "output"
    if not rclone_copy(default_rclone_pull_output(), output):
        print("Error: rclone pull failed.", file=sys.stderr)
        return 1
    print(f"Pulled Drive output to {output}")
    return 0


def cmd_push_input(args: argparse.Namespace) -> int:  # noqa: ARG001
    if not _require_rclone():
        return 1
    root = _repo_root()
    input_dir = root / "input"
    if not input_dir.is_dir():
        print(f"Error: {input_dir} not found.", file=sys.stderr)
        return 1
    if not rclone_copy(str(input_dir), default_rclone_push_input()):
        print("Error: rclone push-input failed.", file=sys.stderr)
        return 1
    print("Pushed local input to Drive.")
    return 0


def cmd_push_output(args: argparse.Namespace) -> int:  # noqa: ARG001
    if not _require_rclone():
        return 1
    root = _repo_root()
    output = root / "output"
    if not output.is_dir():
        print(f"Error: {output} not found.", file=sys.stderr)
        return 1
    if not rclone_copy(str(output), default_rclone_push_output()):
        print("Error: rclone push-output failed.", file=sys.stderr)
        return 1
    print("Pushed local output to Drive.")
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    load_dotenv()
    input_path = _resolve_input_path(args.input)
    output_root = resolve_output_root(args.output, anchor_path=input_path)
    try:
        report = estimate_path(input_path, output_root, force=args.force)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(format_estimate_report(report))
    return 0



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
