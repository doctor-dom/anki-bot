"""Discover and group screenshot files into question items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_CONTAINER_FOLDER_NAMES = {"input", "output", "screenshots", "images", "data", "in"}


@dataclass(frozen=True)
class QuestionGroup:
    id: str
    image_paths: tuple[Path, ...]


def _is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def _sorted_images(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: p.name.lower())


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "question"


# Legacy: item_1.png, item_2.png
_LEGACY_PREFIX_PATTERN = re.compile(
    r"^(?P<prefix>.+?)[_\-.](?P<index>\d+)$",
    re.IGNORECASE,
)


def _numbered_topic_key(stem: str) -> str | None:
    """Parse `<number>-<topic>-<part...>` filenames into a question id.

    Examples:
        12-endocrine-part1       -> 12-endocrine
        12-endocrine-image-2     -> 12-endocrine
        12-endocrine             -> 12-endocrine
        Q12-adrenal-explanation  -> q12-adrenal
    """
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


def discover_questions(root: Path) -> list[QuestionGroup]:
    """Group screenshots into question items.

    Rules (first match wins for loose files):
    1. Filename pattern ``<number>-<topic>-<part>.png`` groups by ``<number>-<topic>``.
    2. Legacy prefix ``name_1.png``, ``name_2.png``.
    3. One subfolder = one question (all images inside that folder).
    4. A folder of unparsed images with no subfolders = one question named after the folder.
    """
    root = root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    groups: list[QuestionGroup] = []

    if root.is_file():
        if _is_image(root):
            key = _numbered_topic_key(root.stem) or _slug(root.stem)
            groups.append(QuestionGroup(id=key, image_paths=(root,)))
        return groups

    subdirs = [p for p in root.iterdir() if p.is_dir()]
    direct_images = [p for p in root.iterdir() if _is_image(p)]

    if direct_images and not subdirs:
        return _group_loose_images(direct_images, folder_name=root.name)

    folder_groups: list[QuestionGroup] = []
    for subdir in sorted(subdirs, key=lambda p: p.name.lower()):
        images = _collect_images_in_dir(subdir)
        if images:
            folder_groups.append(
                QuestionGroup(
                    id=_slug(subdir.name),
                    image_paths=tuple(_sorted_images(images)),
                )
            )

    if folder_groups and not direct_images:
        return folder_groups

    if direct_images and not folder_groups:
        return _group_loose_images(direct_images, folder_name=root.name)

    if folder_groups:
        groups.extend(folder_groups)

    if direct_images:
        groups.extend(_group_loose_images(direct_images, folder_name=root.name))

    if not groups:
        nested = _collect_images_recursive(root)
        if nested:
            if all(_numbered_topic_key(p.stem) for p in nested):
                return _group_loose_images(nested, folder_name=root.name)
            groups.append(
                QuestionGroup(
                    id=_slug(root.name),
                    image_paths=tuple(_sorted_images(nested)),
                )
            )

    return groups


def _collect_images_in_dir(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if _is_image(p)]


def _collect_images_recursive(directory: Path) -> list[Path]:
    found: list[Path] = []
    for path in directory.rglob("*"):
        if _is_image(path):
            found.append(path)
    return found


def _group_loose_images(images: list[Path], *, folder_name: str) -> list[QuestionGroup]:
    by_numbered: dict[str, list[Path]] = {}
    by_legacy: dict[str, list[Path]] = {}
    singles: list[Path] = []

    for image in images:
        numbered = _numbered_topic_key(image.stem)
        if numbered:
            by_numbered.setdefault(numbered, []).append(image)
            continue
        legacy = _legacy_prefix_key(image.stem)
        if legacy:
            by_legacy.setdefault(legacy, []).append(image)
            continue
        singles.append(image)

    if by_numbered:
        groups = [
            QuestionGroup(id=key, image_paths=tuple(_sorted_images(paths)))
            for key, paths in sorted(by_numbered.items())
        ]
        groups.extend(
            QuestionGroup(id=key, image_paths=tuple(_sorted_images(paths)))
            for key, paths in sorted(by_legacy.items())
        )
        groups.extend(
            QuestionGroup(id=_slug(image.stem), image_paths=(image,))
            for image in _sorted_images(singles)
        )
        return groups

    if by_legacy:
        groups = [
            QuestionGroup(id=key, image_paths=tuple(_sorted_images(paths)))
            for key, paths in sorted(by_legacy.items())
        ]
        groups.extend(
            QuestionGroup(id=_slug(image.stem), image_paths=(image,))
            for image in _sorted_images(singles)
        )
        return groups

    if len(images) > 1:
        return [
            QuestionGroup(
                id=_slug(folder_name),
                image_paths=tuple(_sorted_images(images)),
            )
        ]

    image = images[0]
    folder_id = _slug(folder_name)
    if folder_id not in _CONTAINER_FOLDER_NAMES:
        return [QuestionGroup(id=folder_id, image_paths=(image,))]

    return [QuestionGroup(id=_slug(image.stem), image_paths=(image,))]
