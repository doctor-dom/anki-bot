"""Discover and group screenshots, PDF qbanks, and lecture HTML into content items."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

from anki_bot.models import ContentKind

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
HTML_EXTENSIONS = {".html", ".htm"}
PDF_EXTENSIONS = {".pdf"}
_CONTAINER_FOLDER_NAMES = {"input", "output", "screenshots", "images", "data", "in", "lectures"}
_TRACK_NAMES = frozenset({"abp", "endo"})

_QBANK_PDF_PATTERN = re.compile(r"^(\d+)\s+-\s+(.+)$")


@dataclass(frozen=True)
class ContentGroup:
    id: str
    kind: ContentKind
    image_paths: tuple[Path, ...] = ()
    html_paths: tuple[Path, ...] = ()
    pdf_paths: tuple[Path, ...] = ()
    track: str = "misc"


# Backward-compatible alias
QuestionGroup = ContentGroup


def track_from_paths(*paths: Path) -> str:
    """Return abp, endo, or misc from path under input/<track>/..."""
    for path in paths:
        resolved = path.resolve()
        parts = [p.lower() for p in resolved.parts]
        for index, part in enumerate(parts):
            if part == "input" and index + 1 < len(parts):
                candidate = parts[index + 1]
                if candidate in _TRACK_NAMES:
                    return candidate
    return "misc"


def _is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def _is_html(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in HTML_EXTENSIONS


def _is_pdf(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in PDF_EXTENSIONS


def _skip_under_input_output(path: Path) -> bool:
    for parent in path.parents:
        if parent.name.lower() == "output":
            return True
    return False


def _sorted_paths(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: p.name.lower())


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "item"


_LEGACY_PREFIX_PATTERN = re.compile(
    r"^(?P<prefix>.+?)[_\-.](?P<index>\d+)$",
    re.IGNORECASE,
)


def _qbank_pdf_key(stem: str) -> str | None:
    """Parse UWorld-style PDF names: ``10 - T1DM honeymoon`` → ``10-t1dm-honeymoon``."""
    match = _QBANK_PDF_PATTERN.match(stem.strip())
    if not match:
        return None
    number, topic = match.group(1), match.group(2).strip()
    if not topic:
        return None
    return _slug(f"{number}-{topic}")


def _numbered_topic_key(stem: str) -> str | None:
    parts = stem.split("-", 2)
    if len(parts) < 2:
        return None
    number, topic = parts[0].strip(), parts[1].strip()
    if not number or not topic:
        return None
    if not re.match(r"^[A-Za-z0-9]+$", number):
        return None
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9 _]*$", topic):
        return None
    return _slug(f"{number}-{topic}")


def _legacy_prefix_key(stem: str) -> str | None:
    match = _LEGACY_PREFIX_PATTERN.match(stem)
    if match:
        return _slug(match.group("prefix"))
    return None


def _lecture_id(base_id: str) -> str:
    return base_id if base_id.endswith("-lecture") else f"{base_id}-lecture"


def discover_questions(root: Path) -> list[ContentGroup]:
    """Discover question screenshots, PDF qbanks, and lecture HTML under *root*."""
    return discover_content(root)


def discover_content(root: Path) -> list[ContentGroup]:
    root = root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    if root.is_file():
        groups = _discover_single_file(root)
    else:
        groups = _discover_directory(root)

    return _disambiguate_ids(groups)


def _discover_single_file(root: Path) -> list[ContentGroup]:
    track = track_from_paths(root)
    if _is_image(root):
        key = _numbered_topic_key(root.stem) or _slug(root.stem)
        return [
            ContentGroup(
                id=key,
                kind=ContentKind.QUESTION,
                image_paths=(root,),
                track=track,
            )
        ]
    if _is_html(root):
        key = _numbered_topic_key(root.stem) or _slug(root.stem)
        return [
            ContentGroup(
                id=_lecture_id(key),
                kind=ContentKind.LECTURE,
                html_paths=(root,),
                track=track,
            )
        ]
    if _is_pdf(root):
        key = _qbank_pdf_key(root.stem) or _slug(root.stem)
        return [
            ContentGroup(
                id=key,
                kind=ContentKind.QUESTION,
                pdf_paths=(root,),
                track=track,
            )
        ]
    return []


def _discover_directory(directory: Path) -> list[ContentGroup]:
    groups: list[ContentGroup] = []

    direct_pdfs = [p for p in directory.iterdir() if _is_pdf(p)]
    direct_images = [p for p in directory.iterdir() if _is_image(p)]
    direct_html = [p for p in directory.iterdir() if _is_html(p)]

    qbank_pdfs = [p for p in direct_pdfs if _qbank_pdf_key(p.stem)]
    other_pdfs = [p for p in direct_pdfs if p not in qbank_pdfs]

    for path in _sorted_paths(qbank_pdfs):
        key = _qbank_pdf_key(path.stem)
        assert key is not None
        groups.append(
            ContentGroup(
                id=key,
                kind=ContentKind.QUESTION,
                pdf_paths=(path,),
                track=track_from_paths(path),
            )
        )
    for path in _sorted_paths(other_pdfs):
        groups.append(
            ContentGroup(
                id=_slug(path.stem),
                kind=ContentKind.QUESTION,
                pdf_paths=(path,),
                track=track_from_paths(path),
            )
        )

    if direct_images:
        if _use_loose_file_grouping(direct_images):
            groups.extend(
                _group_loose_files(
                    direct_images,
                    kind=ContentKind.QUESTION,
                    folder_name=directory.name,
                )
            )
        else:
            groups.append(
                ContentGroup(
                    id=_slug(directory.name),
                    kind=ContentKind.QUESTION,
                    image_paths=tuple(_sorted_paths(direct_images)),
                    track=track_from_paths(*direct_images),
                )
            )

    if direct_html:
        if _use_loose_file_grouping(direct_html):
            groups.extend(
                _group_loose_files(
                    direct_html,
                    kind=ContentKind.LECTURE,
                    folder_name=directory.name,
                )
            )
        else:
            groups.append(
                ContentGroup(
                    id=_lecture_id(_slug(directory.name)),
                    kind=ContentKind.LECTURE,
                    html_paths=tuple(_sorted_paths(direct_html)),
                    track=track_from_paths(*direct_html),
                )
            )

    child_dirs = [
        p
        for p in directory.iterdir()
        if p.is_dir() and p.name.lower() != "output"
    ]
    for child in sorted(child_dirs, key=lambda p: p.name.lower()):
        groups.extend(_discover_directory(child))

    return groups


def _use_loose_file_grouping(files: list[Path]) -> bool:
    if len(files) == 1:
        return True
    for path in files:
        if _numbered_topic_key(path.stem) or _legacy_prefix_key(path.stem):
            return True
    return False


def _group_folder_slug(group: ContentGroup) -> str:
    if group.pdf_paths:
        return _slug(group.pdf_paths[0].parent.name)
    if group.image_paths:
        return _slug(group.image_paths[0].parent.name)
    if group.html_paths:
        return _slug(group.html_paths[0].parent.name)
    return "item"


def _disambiguate_ids(groups: list[ContentGroup]) -> list[ContentGroup]:
    by_id: dict[str, list[ContentGroup]] = {}
    for group in groups:
        by_id.setdefault(group.id, []).append(group)

    result: list[ContentGroup] = []
    for group_id, bucket in by_id.items():
        if len(bucket) == 1:
            result.append(bucket[0])
            continue
        for group in bucket:
            parent_slug = _group_folder_slug(group)
            new_id = _slug(f"{parent_slug}-{group_id}")
            result.append(replace(group, id=new_id))
    return sorted(result, key=lambda g: g.id)


def _group_loose_files(
    files: list[Path],
    *,
    kind: ContentKind,
    folder_name: str,
) -> list[ContentGroup]:
    if not files:
        return []

    by_numbered: dict[str, list[Path]] = {}
    by_legacy: dict[str, list[Path]] = {}
    singles: list[Path] = []

    for path in files:
        numbered = _numbered_topic_key(path.stem)
        if numbered:
            by_numbered.setdefault(numbered, []).append(path)
            continue
        legacy = _legacy_prefix_key(path.stem)
        if legacy:
            by_legacy.setdefault(legacy, []).append(path)
            continue
        singles.append(path)

    def _make_group(group_id: str, paths: list[Path]) -> ContentGroup:
        final_id = _lecture_id(group_id) if kind == ContentKind.LECTURE else group_id
        sorted_paths = _sorted_paths(paths)
        track = track_from_paths(*sorted_paths)
        if kind == ContentKind.QUESTION:
            return ContentGroup(
                id=final_id,
                kind=kind,
                image_paths=tuple(sorted_paths),
                track=track,
            )
        return ContentGroup(
            id=final_id,
            kind=kind,
            html_paths=tuple(sorted_paths),
            track=track,
        )

    if by_numbered:
        groups = [_make_group(key, paths) for key, paths in sorted(by_numbered.items())]
        groups.extend(_make_group(key, paths) for key, paths in sorted(by_legacy.items()))
        groups.extend(_make_group(_slug(path.stem), [path]) for path in _sorted_paths(singles))
        return groups

    if by_legacy:
        groups = [_make_group(key, paths) for key, paths in sorted(by_legacy.items())]
        groups.extend(_make_group(_slug(path.stem), [path]) for path in _sorted_paths(singles))
        return groups

    if len(files) > 1:
        folder_id = _slug(folder_name)
        final_id = _lecture_id(folder_id) if kind == ContentKind.LECTURE else folder_id
        sorted_paths = _sorted_paths(files)
        track = track_from_paths(*sorted_paths)
        if kind == ContentKind.QUESTION:
            return [
                ContentGroup(
                    id=final_id,
                    kind=kind,
                    image_paths=tuple(sorted_paths),
                    track=track,
                )
            ]
        return [
            ContentGroup(
                id=final_id,
                kind=kind,
                html_paths=tuple(sorted_paths),
                track=track,
            )
        ]

    path = files[0]
    folder_id = _slug(folder_name)
    if folder_id not in _CONTAINER_FOLDER_NAMES:
        final_id = _lecture_id(folder_id) if kind == ContentKind.LECTURE else folder_id
    else:
        final_id = _lecture_id(_slug(path.stem)) if kind == ContentKind.LECTURE else _slug(path.stem)

    track = track_from_paths(path)
    if kind == ContentKind.QUESTION:
        return [ContentGroup(id=final_id, kind=kind, image_paths=(path,), track=track)]
    return [ContentGroup(id=final_id, kind=kind, html_paths=(path,), track=track)]
