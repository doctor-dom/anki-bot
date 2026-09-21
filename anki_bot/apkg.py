"""Build Anki .apkg packages from validated review JSON."""

from __future__ import annotations

import hashlib
import random
import re
from pathlib import Path

import genanki

from anki_bot.media import append_image_tags, media_basenames_for_review, target_card_index

# Allowed inline HTML from anki-bot cloze cards (hy-* spans and stem Extra images).
_ALLOWED_TAG_RE = re.compile(
    r"</span>|<span\s+class=\"hy-(?:topic|neg|dx|tx|diff)\"\s*>|<img\s+src=\"[^\"]+\"\s*/?>",
    re.IGNORECASE,
)

MODEL_ID = 1607395104

CARD_CSS = """
.card {
  font-family: arial;
  font-size: 18px;
  text-align: left;
  color: black;
  background-color: white;
}
.hy-topic { color: #111111; font-weight: bold; }
.hy-neg { color: #c0392b; }
.hy-dx { color: #2471a3; }
.hy-tx { color: #1e8449; }
.hy-diff { color: #7d3c98; }
.extra { margin-top: 1em; font-size: 0.9em; color: #444; }
.extra img { max-width: 100%; height: auto; display: block; margin-top: 0.5em; }
.nightMode .card { color: #eee; background-color: #2f2f2f; }
.nightMode .hy-topic { color: #f0f0f0; }
.nightMode .hy-neg { color: #e74c3c; }
.nightMode .hy-dx { color: #5dade2; }
.nightMode .hy-tx { color: #58d68d; }
.nightMode .hy-diff { color: #bb8fce; }
.nightMode .extra { color: #ccc; }
"""


def stable_id(name: str, *, minimum: int = 1 << 20) -> int:
    """Derive a stable positive integer id from a string label."""
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return minimum + (int(digest[:8], 16) % (1 << 20))


def deck_id_for_name(deck_name: str) -> int:
    return stable_id(f"deck::{deck_name}")


def _escape_literal_lt(text: str) -> str:
    """Escape raw ``<`` as ``&lt;`` without double-escaping existing entities."""
    out: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith("&lt;", index):
            out.append("&lt;")
            index += 4
            continue
        if text[index] == "<":
            out.append("&lt;")
            index += 1
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def escape_field_for_genanki(field: str) -> str:
    """
    Escape medical ``<`` (e.g. ``< 24 months``) for genanki while keeping hy-* spans.
    """
    if not field:
        return field

    parts: list[str] = []
    last = 0
    for match in _ALLOWED_TAG_RE.finditer(field):
        parts.append(_escape_literal_lt(field[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_escape_literal_lt(field[last:]))
    return "".join(parts)


def cloze_model() -> genanki.Model:
    return genanki.Model(
        MODEL_ID,
        "anki-bot Cloze",
        fields=[
            {"name": "Text"},
            {"name": "Extra"},
        ],
        templates=[
            {
                "name": "Cloze",
                "qfmt": "{{cloze:Text}}",
                "afmt": "{{cloze:Text}}<div class='extra'>{{Extra}}</div>",
            },
        ],
        model_type=genanki.Model.CLOZE,
        css=CARD_CSS,
    )


def build_deck(reviews: list, deck_name: str = "HUB::anki-bot") -> tuple[genanki.Deck, list[str]]:
    deck = genanki.Deck(deck_id_for_name(deck_name), deck_name)
    model = cloze_model()
    media_files: list[str] = []

    for review in reviews:
        entries = media_basenames_for_review(review)
        basenames = [name for _, name in entries]
        media_files.extend(str(path) for path, _ in entries)
        image_target = target_card_index(review)

        for index, card in enumerate(review.cards):
            extra = card.extra or ""
            if index == image_target and basenames:
                extra = append_image_tags(extra, basenames)
            note = genanki.Note(
                model=model,
                fields=[
                    escape_field_for_genanki(card.text),
                    escape_field_for_genanki(extra),
                ],
                tags=card.tags or [f"anki-bot::{review.id}"],
            )
            deck.add_note(note)

    unique_media = list(dict.fromkeys(media_files))
    return deck, unique_media


def write_apkg(
    reviews: list,
    output_path: Path,
    deck_name: str = "HUB::anki-bot",
) -> int:
    """Write .apkg and return note count."""
    deck, media_files = build_deck(reviews, deck_name=deck_name)
    note_count = len(deck.notes)
    if note_count == 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return 0

    package = genanki.Package(deck)
    if media_files:
        package.media_files = media_files
    output_path.parent.mkdir(parents=True, exist_ok=True)
    package.write_to_file(str(output_path))
    return note_count


def random_note_id() -> int:
    return random.randrange(1 << 30, 1 << 31)
