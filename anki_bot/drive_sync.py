"""Google Drive / rclone paths, discover union, remote review fetch."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from anki_bot.discover import ContentGroup, discover_content
from anki_bot.models import QuestionReview


def _env_path(key: str) -> Path | None:
    raw = os.getenv(key, "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_dir():
        return path.resolve()
    return None


def _env_rclone_spec(key: str, default_suffix: str) -> str | None:
    raw = os.getenv(key, "").strip()
    if raw:
        return raw
    remote = os.getenv("ANKI_BOT_RCLONE_REMOTE", "gdrive").strip()
    if not remote:
        return None
    return f"{remote}:anki-bot/{default_suffix}"


def resolve_drive_input() -> Path | None:
    """Local folder (Drive for Desktop) or None if only rclone spec is configured."""
    return _env_path("ANKI_BOT_DRIVE_INPUT")


def drive_input_rclone_spec() -> str | None:
    mounted = resolve_drive_input()
    if mounted is not None:
        return None
    return _env_rclone_spec("ANKI_BOT_DRIVE_INPUT", "input")


def resolve_drive_output_dir() -> Path | None:
    return _env_path("ANKI_BOT_DRIVE_OUTPUT")


def drive_output_rclone_spec() -> str | None:
    mounted = resolve_drive_output_dir()
    if mounted is not None:
        return None
    return _env_rclone_spec("ANKI_BOT_DRIVE_OUTPUT", "output")


def rclone_available() -> bool:
    try:
        subprocess.run(
            ["rclone", "version"],
            check=False,
            capture_output=True,
            timeout=30,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def rclone_copyto(remote_spec: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["rclone", "copyto", remote_spec, str(dest)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode == 0 and dest.is_file()


def rclone_copy(src: str | Path, dest: str | Path) -> bool:
    if isinstance(dest, Path):
        dest.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["rclone", "copy", str(src), str(dest)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return result.returncode == 0


def default_rclone_pull_output() -> str:
    remote = os.getenv("ANKI_BOT_RCLONE_REMOTE", "gdrive")
    return f"{remote}:anki-bot/output"


def default_rclone_push_output() -> str:
    remote = os.getenv("ANKI_BOT_RCLONE_REMOTE", "gdrive")
    return f"{remote}:anki-bot/output"


def default_rclone_push_input() -> str:
    remote = os.getenv("ANKI_BOT_RCLONE_REMOTE", "gdrive")
    return f"{remote}:anki-bot/input"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _all_source_paths(group: ContentGroup) -> list[Path]:
    return list(group.pdf_paths) + list(group.image_paths) + list(group.html_paths)


def group_content_signature(group: ContentGroup) -> frozenset[tuple[str, int]]:
    """Hash + size per source file; same content on local and Drive dedupes to one group."""
    sigs: set[tuple[str, int]] = set()
    for path in _all_source_paths(group):
        sigs.add((file_sha256(path), path.stat().st_size))
    return frozenset(sigs)


def discover_with_drive(local_root: Path) -> tuple[list[ContentGroup], list[Path], list[str]]:
    """
    Discover under local_root and optional Drive input mirror.

    Returns (groups, input_roots for fingerprints, warnings).
    """
    warnings: list[str] = []
    local_root = local_root.resolve()
    input_roots: list[Path] = [local_root]
    groups = discover_content(local_root)

    drive_dir = resolve_drive_input()
    if drive_dir is not None:
        input_roots.append(drive_dir)
        drive_groups = discover_content(drive_dir)
        groups = _merge_group_lists(groups, drive_groups)
        return groups, input_roots, warnings

    spec = drive_input_rclone_spec()
    if spec and rclone_available():
        with tempfile.TemporaryDirectory(prefix="anki-bot-drive-in-") as tmp:
            tmp_path = Path(tmp)
            if rclone_copy(spec, tmp_path):
                input_roots.append(tmp_path)
                drive_groups = discover_content(tmp_path)
                groups = _merge_group_lists(groups, drive_groups)
            else:
                warnings.append(f"Could not rclone copy {spec}; using local input only.")
    elif spec and not rclone_available():
        warnings.append("ANKI_BOT_DRIVE_INPUT is rclone but rclone is not on PATH; local input only.")

    return groups, input_roots, warnings


def _merge_group_lists(
    local_groups: list[ContentGroup],
    drive_groups: list[ContentGroup],
) -> list[ContentGroup]:
    merged: dict[frozenset[tuple[str, int]], ContentGroup] = {}
    for group in local_groups:
        merged[group_content_signature(group)] = group
    for group in drive_groups:
        sig = group_content_signature(group)
        if sig in merged:
            continue
        merged[sig] = group
    return sorted(merged.values(), key=lambda g: g.id.lower())


def load_review_json(path: Path) -> QuestionReview | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return QuestionReview.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None


def fetch_drive_review(group_id: str) -> QuestionReview | None:
    """Load review JSON from Drive output (mounted folder or rclone copyto)."""
    mounted = resolve_drive_output_dir()
    if mounted is not None:
        return load_review_json(mounted / "reviews" / f"{group_id}.json")

    spec = drive_output_rclone_spec()
    if not spec or not rclone_available():
        return None

    remote = f"{spec.rstrip('/')}/reviews/{group_id}.json"
    with tempfile.TemporaryDirectory(prefix="anki-bot-review-") as tmp:
        dest = Path(tmp) / f"{group_id}.json"
        if not rclone_copyto(remote, dest):
            return None
        return load_review_json(dest)
