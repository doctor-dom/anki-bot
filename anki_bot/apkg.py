"""Build Anki .apkg packages from validated review JSON."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

import genanki

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


def build_deck(reviews: list, deck_name: str = "HUB::anki-bot") -> genanki.Deck:
    deck = genanki.Deck(deck_id_for_name(deck_name), deck_name)
    model = cloze_model()

    for review in reviews:
        for card in review.cards:
            note = genanki.Note(
                model=model,
                fields=[card.text, card.extra or ""],
                tags=card.tags or [f"anki-bot::{review.id}"],
            )
            deck.add_note(note)

    return deck


def write_apkg(
    reviews: list,
    output_path: Path,
    deck_name: str = "HUB::anki-bot",
) -> int:
    """Write .apkg and return note count."""
    deck = build_deck(reviews, deck_name=deck_name)
    note_count = len(deck.notes)
    if note_count == 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return 0

    package = genanki.Package(deck)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    package.write_to_file(str(output_path))
    return note_count


def random_note_id() -> int:
    return random.randrange(1 << 30, 1 << 31)
