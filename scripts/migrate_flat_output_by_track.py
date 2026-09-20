#!/usr/bin/env python3
"""Move flat repo-root output/reviews and packs into output/<track>/."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from anki_bot.outputs import normalize_track, topic_from_group_id
from anki_bot.paths import find_repo_root


def _repo_root() -> Path:
    root = find_repo_root(Path.cwd())
    if root is None:
        raise SystemExit("Could not find pyproject.toml (run from repo root).")
    return root


def _track_from_review(data: dict) -> str:
    return normalize_track(data.get("track") or "misc")


def migrate(*, dry_run: bool) -> int:
    repo = _repo_root()
    output = repo / "output"
    flat_reviews = output / "reviews"
    flat_ankideck = output / "ankideck"
    if not flat_reviews.is_dir() and not flat_ankideck.is_dir():
        print("No flat output/reviews or output/ankideck found.")
        return 0

    moved_reviews = 0
    lecture_stems_by_track: dict[str, set[str]] = {}

    if flat_reviews.is_dir():
        for json_path in sorted(flat_reviews.glob("*.json")):
            data = json.loads(json_path.read_text(encoding="utf-8"))
            review_id = data.get("id") or json_path.stem
            track = _track_from_review(data)
            dest_dir = output / track / "reviews"
            dest_json = dest_dir / f"{review_id}.json"
            print(f"{'Would move' if dry_run else 'Move'} {json_path} -> {dest_json}")
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(json_path), str(dest_json))

            html_src = flat_reviews / f"{review_id}.html"
            if html_src.is_file():
                dest_html = dest_dir / f"{review_id}.html"
                print(f"{'Would move' if dry_run else 'Move'} {html_src} -> {dest_html}")
                if not dry_run:
                    shutil.move(str(html_src), str(dest_html))

            moved_reviews += 1
            if review_id.endswith("-lecture") or data.get("kind") == "lecture":
                stem = topic_from_group_id(review_id)
                lecture_stems_by_track.setdefault(track, set()).add(stem)

    if flat_ankideck.is_dir():
        for apkg in sorted(flat_ankideck.glob("*.apkg")):
            track = _track_from_apkg_name(apkg.name, lecture_stems_by_track)
            dest = output / track / "ankideck" / apkg.name
            print(f"{'Would move' if dry_run else 'Move'} {apkg} -> {dest}")
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(apkg), str(dest))

    for html in sorted(output.glob("qbank*-high-yield.html")):
        track = _track_from_qbank_html(html.name)
        dest = output / track / html.name
        print(f"{'Would move' if dry_run else 'Move'} {html} -> {dest}")
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(html), str(dest))

    for html in sorted(output.glob("*-high-yield.html")):
        if html.name.startswith("qbank"):
            continue
        stem = html.name[: -len("-high-yield.html")]
        track = _track_for_lecture_stem(stem, lecture_stems_by_track)
        dest = output / track / html.name
        print(f"{'Would move' if dry_run else 'Move'} {html} -> {dest}")
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(html), str(dest))

    if not dry_run and flat_reviews.is_dir() and not any(flat_reviews.iterdir()):
        flat_reviews.rmdir()
        print(f"Removed empty {flat_reviews}")
    if not dry_run and flat_ankideck.is_dir() and not any(flat_ankideck.iterdir()):
        flat_ankideck.rmdir()
        print(f"Removed empty {flat_ankideck}")

    print(f"Done. Migrated {moved_reviews} review JSON file(s).")
    return 0


def _track_from_apkg_name(name: str, lecture_stems: dict[str, set[str]]) -> str:
    if name.startswith("qbank-"):
        match = re.match(r"^qbank-([a-z0-9-]+?)(\d+)?\.apkg$", name)
        if match:
            return normalize_track(match.group(1))
    stem = name[: -len(".apkg")]
    return _track_for_lecture_stem(stem, lecture_stems)


def _track_from_qbank_html(name: str) -> str:
    match = re.match(r"^qbank-([a-z0-9-]+?)(\d+)?-high-yield\.html$", name)
    if match:
        return normalize_track(match.group(1))
    return "misc"


def _track_for_lecture_stem(stem: str, lecture_stems: dict[str, set[str]]) -> str:
    for track, stems in lecture_stems.items():
        if stem in stems:
            return track
    return "misc"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate flat output/reviews and packs to output/<track>/",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    args = parser.parse_args()
    raise SystemExit(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
