"""Discover and group screenshot and lecture HTML files into content items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from anki_bot.models import ContentKind

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
HTML_EXTENSIONS = {".html", ".htm"}
_CONTAINER_FOLDER_NAMES = {"input", "output", "screenshots", "images", "data", "in", "lectures"}


@dataclass(frozen=True)
class ContentGroup:
    id: str
    kind: ContentKind
    image_paths: tuple[Path, ...] = ()
    html_paths: tuple[Path, ...] = ()


# Backward-compatible alias
QuestionGroup = ContentGroup


def _is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def _is_html(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in HTML_EXTENSIONS


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
    """Discover question screenshots and lecture HTML files under *root*."""
    return discover_content(root)


def discover_content(root: Path) -> list[ContentGroup]:
    root = root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    groups: list[ContentGroup] = []

    if root.is_file():
        if _is_image(root):
            key = _numbered_topic_key(root.stem) or _slug(root.stem)
            groups.append(
                ContentGroup(
                    id=key,
                    kind=ContentKind.QUESTION,
                    image_paths=(root,),
                )
            )
        elif _is_html(root):
            key = _numbered_topic_key(root.stem) or _slug(root.stem)
            groups.append(
                ContentGroup(
                    id=_lecture_id(key),
                    kind=ContentKind.LECTURE,
                    html_paths=(root,),
                )
            )
        return groups

    subdirs = [p for p in root.iterdir() if p.is_dir()]
    direct_images = [p for p in root.iterdir() if _is_image(p)]
    direct_html = [p for p in root.iterdir() if _is_html(p)]

    if (direct_images or direct_html) and not subdirs:
        groups.extend(_group_loose_files(direct_images, kind=ContentKind.QUESTION, folder_name=root.name))
        groups.extend(_group_loose_files(direct_html, kind=ContentKind.LECTURE, folder_name=root.name))
        return groups

    for subdir in sorted(subdirs, key=lambda p: p.name.lower()):
        images = _collect_files(subdir, _is_image)
        html_files = _collect_files(subdir, _is_html)
        if images:
            groups.append(
                ContentGroup(
                    id=_slug(subdir.name),
                    kind=ContentKind.QUESTION,
                    image_paths=tuple(_sorted_paths(images)),
                )
            )
        if html_files:
            groups.append(
                ContentGroup(
                    id=_lecture_id(_slug(subdir.name)),
                    kind=ContentKind.LECTURE,
                    html_paths=tuple(_sorted_paths(html_files)),
                )
            )

    if direct_images:
        groups.extend(
            _group_loose_files(direct_images, kind=ContentKind.QUESTION, folder_name=root.name)
        )
    if direct_html:
        groups.extend(
            _group_loose_files(direct_html, kind=ContentKind.LECTURE, folder_name=root.name)
        )

    if not groups:
        nested_images = _collect_recursive(root, _is_image)
        nested_html = _collect_recursive(root, _is_html)
        if nested_images:
            if all(_numbered_topic_key(p.stem) for p in nested_images):
                groups.extend(
                    _group_loose_files(nested_images, kind=ContentKind.QUESTION, folder_name=root.name)
                )
            else:
                groups.append(
                    ContentGroup(
                        id=_slug(root.name),
                        kind=ContentKind.QUESTION,
                        image_paths=tuple(_sorted_paths(nested_images)),
                    )
                )
        if nested_html:
            if all(_numbered_topic_key(p.stem) for p in nested_html):
                groups.extend(
                    _group_loose_files(nested_html, kind=ContentKind.LECTURE, folder_name=root.name)
                )
            else:
                groups.append(
                    ContentGroup(
                        id=_lecture_id(_slug(root.name)),
                        kind=ContentKind.LECTURE,
                        html_paths=tuple(_sorted_paths(nested_html)),
                    )
                )

    return groups


def _collect_files(directory: Path, predicate) -> list[Path]:
    return [p for p in directory.iterdir() if predicate(p)]


def _collect_recursive(directory: Path, predicate) -> list[Path]:
    return [path for path in directory.rglob("*") if predicate(path)]


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
        if kind == ContentKind.QUESTION:
            return ContentGroup(
                id=final_id,
                kind=kind,
                image_paths=tuple(_sorted_paths(paths)),
            )
        return ContentGroup(
            id=final_id,
            kind=kind,
            html_paths=tuple(_sorted_paths(paths)),
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
        if kind == ContentKind.QUESTION:
            return [
                ContentGroup(
                    id=final_id,
                    kind=kind,
                    image_paths=tuple(_sorted_paths(files)),
                )
            ]
        return [
            ContentGroup(
                id=final_id,
                kind=kind,
                html_paths=tuple(_sorted_paths(files)),
            )
        ]

    path = files[0]
    folder_id = _slug(folder_name)
    if folder_id not in _CONTAINER_FOLDER_NAMES:
        final_id = _lecture_id(folder_id) if kind == ContentKind.LECTURE else folder_id
    else:
        final_id = _lecture_id(_slug(path.stem)) if kind == ContentKind.LECTURE else _slug(path.stem)

    if kind == ContentKind.QUESTION:
        return [ContentGroup(id=final_id, kind=kind, image_paths=(path,))]
    return [ContentGroup(id=final_id, kind=kind, html_paths=(path,))]
