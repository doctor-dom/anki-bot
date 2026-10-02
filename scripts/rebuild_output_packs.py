#!/usr/bin/env python3
"""Rebuild all-track, topic, and per-folder packs from existing review JSON (no Gemini).

After pulling Drive ``output/`` locally::

    python scripts/rebuild_output_packs.py output

Then sync back: ``rclone sync ./output gdrive:anki-bot/output``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from anki_bot.pipeline import build_from_reviews


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_root",
        type=Path,
        nargs="?",
        default=Path("output"),
        help="Output root (default: ./output)",
    )
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    if not output_root.is_dir():
        print(f"Not a directory: {output_root}", file=sys.stderr)
        return 1
    reviews, note_count = build_from_reviews(output_root, output_root)
    print(f"Rebuilt packs from {len(reviews)} review(s); {note_count} note(s) in .apkg files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
