#!/usr/bin/env python3
"""Move nested input/**/output trees into repo-root output/."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from anki_bot.outputs import topic_from_group_id
from anki_bot.paths import find_repo_root


def _repo_root() -> Path:
    root = find_repo_root(Path.cwd())
    if root is None:
        raise SystemExit("Could not find pyproject.toml (run from repo root).")
    return root


def _track_from_nested_path(nested_output: Path, repo: Path) -> str:
    try:
        rel = nested_output.relative_to(repo / "input")
        if rel.parts:
            track = rel.parts[0].lower()
            if track in {"abp", "endo"}:
                return track
    except ValueError:
        pass
    return "misc"


def _lecture_pack_stem(review_id: str) -> str:
    return topic_from_group_id(review_id)


def migrate(*, dry_run: bool) -> int:
    repo = _repo_root()
    dest_reviews = repo / "output" / "reviews"
    dest_root = repo / "output"
    dest_ankideck = dest_root / "ankideck"
    nested_dirs = sorted(repo.glob("input/**/output"))
    if not nested_dirs:
        print("No nested input/**/output directories found.")
        return 0

    moved = 0
    for nested in nested_dirs:
        if not nested.is_dir():
            continue
        track = _track_from_nested_path(nested, repo)
        reviews_src = nested / "reviews"
        if reviews_src.is_dir():
            for json_path in sorted(reviews_src.glob("*.json")):
                data = json.loads(json_path.read_text(encoding="utf-8"))
                review_id = data.get("id") or json_path.stem
                data["track"] = data.get("track") or track
                dest_json = dest_reviews / f"{review_id}.json"
                print(f"{'Would move' if dry_run else 'Move'} review {json_path} -> {dest_json}")
                if not dry_run:
                    dest_reviews.mkdir(parents=True, exist_ok=True)
                    dest_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                moved += 1

                html_src = reviews_src / f"{review_id}.html"
                if html_src.is_file():
                    dest_html = dest_reviews / f"{review_id}.html"
                    print(f"{'Would move' if dry_run else 'Move'} preview {html_src} -> {dest_html}")
                    if not dry_run:
                        shutil.copy2(html_src, dest_html)

                if review_id.endswith("-lecture") or data.get("kind") == "lecture":
                    stem = _lecture_pack_stem(review_id)
                    for name in (f"{stem}.apkg", f"{stem}-high-yield.html"):
                        src = nested / name
                        if src.is_file():
                            dest = (
                                dest_ankideck / name
                                if name.endswith(".apkg")
                                else dest_root / name
                            )
                            print(f"{'Would move' if dry_run else 'Move'} pack {src} -> {dest}")
                            if not dry_run:
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(src, dest)
                    for alt in nested.glob("*.apkg"):
                        if alt.stem != stem and alt.stem.endswith("-lecture"):
                            continue
                        if alt.stem == review_id:
                            dest = dest_ankideck / f"{stem}.apkg"
                            if not dry_run:
                                dest_ankideck.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(alt, dest)

        for apkg in nested.glob("qbank*.apkg"):
            dest = dest_ankideck / apkg.name
            print(f"{'Would move' if dry_run else 'Move'} {apkg} -> {dest}")
            if not dry_run:
                dest_ankideck.mkdir(parents=True, exist_ok=True)
                shutil.copy2(apkg, dest)
        for html in nested.glob("qbank*-high-yield.html"):
            dest = dest_root / html.name
            print(f"{'Would move' if dry_run else 'Move'} {html} -> {dest}")
            if not dry_run:
                shutil.copy2(html, dest)

        for loose in nested.glob("*-high-yield.html"):
            if loose.name.startswith("qbank"):
                continue
            dest = dest_root / loose.name
            if not dest.exists():
                print(f"{'Would move' if dry_run else 'Move'} {loose} -> {dest}")
                if not dry_run:
                    shutil.copy2(loose, dest)

        if not dry_run:
            shutil.rmtree(nested)
            print(f"Removed nested output directory: {nested}")

    print(f"Done. Migrated {moved} review JSON file(s).")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate nested input/**/output to repo output/")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without copying or deleting")
    args = parser.parse_args()
    raise SystemExit(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
