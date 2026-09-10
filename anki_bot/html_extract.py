"""Extract readable text and lecture metadata from HTML files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from anki_bot.outputs import slugify_label, topic_from_group_id

MAX_LECTURE_CHARS = 120_000

HOURS_META_NAMES = frozenset({"lecture-hours", "duration", "lecture-duration"})
TOPIC_META_NAMES = frozenset({"lecture-topic", "topic"})


@dataclass
class LectureMeta:
    hours: float | None = None
    topic: str | None = None
    warnings: list[str] = field(default_factory=list)


class _TextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "meta":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            name = attr_map.get("name", "").lower()
            content = attr_map.get("content", "").strip()
            if name and content:
                self.meta[name] = content
            return

        if tag_lower in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag_lower == "head":
            self._skip_depth += 1
            return
        if tag_lower in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag_lower == "head" and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        raw = " ".join(self._chunks)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return raw.strip()


def parse_duration(value: str) -> float | None:
    """Parse duration strings like ``1.5``, ``1.5h``, ``90min``, ``1:30``."""
    raw = value.strip().lower()
    if not raw:
        return None

    if ":" in raw:
        parts = raw.split(":", 1)
        try:
            hours = int(parts[0])
            minutes = int(parts[1].rstrip("h"))
            return hours + minutes / 60.0
        except ValueError:
            return None

    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|min|mins|minute|minutes)?", raw)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2) or "h"
    if unit.startswith("min"):
        return amount / 60.0
    return amount


def _meta_value(meta: dict[str, str], names: frozenset[str]) -> str | None:
    for name in names:
        if name in meta:
            return meta[name]
    return None


def parse_lecture_meta_from_html(raw_html: str) -> LectureMeta:
    parser = _TextExtractor()
    parser.feed(raw_html)
    meta = parser.meta
    warnings: list[str] = []

    hours_raw = _meta_value(meta, HOURS_META_NAMES)
    hours = parse_duration(hours_raw) if hours_raw else None
    if hours_raw and hours is None:
        warnings.append(f"Could not parse lecture duration meta value: {hours_raw!r}")

    topic_raw = _meta_value(meta, TOPIC_META_NAMES)
    topic = slugify_label(topic_raw) if topic_raw else None

    return LectureMeta(hours=hours, topic=topic, warnings=warnings)


def parse_lecture_meta(paths: list[Path], *, group_id: str | None = None) -> LectureMeta:
    """Read lecture-hours and lecture-topic meta from HTML file(s)."""
    combined = LectureMeta()
    for path in paths:
        raw_html = path.read_text(encoding="utf-8", errors="replace")
        file_meta = parse_lecture_meta_from_html(raw_html)
        if combined.hours is None and file_meta.hours is not None:
            combined.hours = file_meta.hours
        if combined.topic is None and file_meta.topic is not None:
            combined.topic = file_meta.topic
        combined.warnings.extend(file_meta.warnings)

    if combined.topic is None and group_id:
        combined.topic = topic_from_group_id(group_id)

    return combined


def extract_html_text(path: Path) -> str:
    raw_html = path.read_text(encoding="utf-8", errors="replace")
    parser = _TextExtractor()
    parser.feed(raw_html)
    return parser.get_text()


def combine_lecture_html(
    paths: list[Path],
    *,
    group_id: str | None = None,
) -> tuple[str, list[str], LectureMeta]:
    """Return combined lecture text, warnings, and parsed metadata."""
    warnings: list[str] = []
    sections: list[str] = []
    meta = parse_lecture_meta(paths, group_id=group_id)

    for path in paths:
        text = extract_html_text(path)
        if not text:
            warnings.append(f"No extractable text in {path.name}")
            continue
        sections.append(f"=== {path.name} ===\n{text}")

    combined = "\n\n".join(sections).strip()
    if len(combined) > MAX_LECTURE_CHARS:
        warnings.append(
            f"Lecture text truncated from {len(combined)} to {MAX_LECTURE_CHARS} characters"
        )
        combined = combined[:MAX_LECTURE_CHARS]

    warnings.extend(meta.warnings)
    return combined, warnings, meta
