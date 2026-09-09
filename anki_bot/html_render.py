"""Render standalone high-yield HTML and per-item review previews."""

from __future__ import annotations

from html import escape
from pathlib import Path

from anki_bot.models import CATEGORY_CSS, Category, QuestionReview, topic_heading

LIST_CSS = """
:root {
  --hy-topic: #111111;
  --hy-neg: #c0392b;
  --hy-dx: #2471a3;
  --hy-tx: #1e8449;
  --hy-diff: #7d3c98;
  --bg: #fafafa;
  --border: #ddd;
  --muted: #666;
}
* { box-sizing: border-box; }
body {
  font-family: "Segoe UI", system-ui, sans-serif;
  line-height: 1.5;
  max-width: 960px;
  margin: 0 auto;
  padding: 1.5rem;
  background: var(--bg);
  color: #222;
}
h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
.subtitle { color: var(--muted); margin-bottom: 1.5rem; }
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  margin-bottom: 2rem;
  font-size: 0.9rem;
}
.legend span { font-weight: 600; }
.hy-topic { color: var(--hy-topic); font-weight: 700; }
.hy-neg { color: var(--hy-neg); }
.hy-dx { color: var(--hy-dx); }
.hy-tx { color: var(--hy-tx); }
.hy-diff { color: var(--hy-diff); }
.section {
  margin-bottom: 2rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border);
}
.section:last-child { border-bottom: none; }
.section-meta {
  font-size: 0.8rem;
  color: var(--muted);
  margin-bottom: 0.5rem;
}
.section-title {
  font-size: 1.15rem;
  margin: 0 0 0.75rem;
}
.hy-item {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.75rem;
  padding: 0.6rem 0.75rem;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-bottom: 0.5rem;
}
.hy-item span::after { content: " ·"; color: var(--muted); }
.hy-item span:last-child::after { content: ""; }
.warnings {
  margin-top: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: #fff3cd;
  border-radius: 6px;
  font-size: 0.85rem;
}
.preview-block { margin-top: 1rem; }
.preview-block h3 { font-size: 1rem; margin-bottom: 0.35rem; }
.card-preview {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  font-size: 0.95rem;
}
"""


def _span(text: str, css_class: str) -> str:
    return f'<span class="{css_class}">{escape(text)}</span>'


def render_high_yield_item_html(review: QuestionReview) -> str:
    """One clustered row for the running list."""
    if not review.high_yield:
        return ""

    parts: list[str] = []
    for item in review.high_yield:
        css = CATEGORY_CSS.get(item.category, "hy-topic")
        parts.append(_span(item.text, css))

    return f'<div class="hy-item">{"".join(parts)}</div>'


def render_high_yield_section(review: QuestionReview) -> str:
    heading = topic_heading(review)
    meta = escape(review.processed_at or review.id)
    item_html = render_high_yield_item_html(review)
    warnings_html = ""
    if review.warnings:
        items = "".join(f"<li>{escape(w)}</li>" for w in review.warnings)
        warnings_html = f'<div class="warnings"><strong>Warnings</strong><ul>{items}</ul></div>'

    return f"""
<section class="section" id="{escape(review.id)}">
  <div class="section-meta">{meta} · {escape(review.id)}</div>
  <h2 class="section-title hy-topic">{escape(heading)}</h2>
  {item_html}
  {warnings_html}
</section>
""".strip()


def render_high_yield_page(reviews: list[QuestionReview], title: str = "High-Yield List") -> str:
    sections = "\n".join(render_high_yield_section(r) for r in reviews if r.high_yield)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{LIST_CSS}</style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p class="subtitle">Running color-coded pearls from anki-bot. Edit JSON in output/reviews/, then rebuild.</p>
  <div class="legend">
    <span class="hy-topic">Topic</span>
    <span class="hy-neg">Signs / neg</span>
    <span class="hy-dx">Diagnosis / testing</span>
    <span class="hy-tx">Treatment / pos</span>
    <span class="hy-diff">Distinctions</span>
  </div>
  {sections or '<p>No high-yield items yet.</p>'}
</body>
</html>
"""


def render_item_preview(review: QuestionReview) -> str:
    section = render_high_yield_section(review)
    cards_html = ""
    if review.cards:
        blocks = []
        for i, card in enumerate(review.cards, start=1):
            extra = f'<div class="card-extra">{card.extra}</div>' if card.extra else ""
            blocks.append(
                f'<div class="card-preview"><strong>Card {i}</strong><div>{card.text}</div>{extra}</div>'
            )
        cards_html = f'<div class="preview-block"><h3>Proposed cloze cards</h3>{"".join(blocks)}</div>'

    stem = escape(review.item.stem_gist)
    clues = ", ".join(escape(c) for c in review.stem_clues)
    distractors = ""
    if review.distractors:
        rows = []
        for d in review.distractors:
            rows.append(
                f"<li><strong>{escape(d.letter)}</strong> {escape(d.text)} — "
                f"{escape(d.why_wrong or d.reusable_fact)}</li>"
            )
        distractors = f'<div class="preview-block"><h3>Distractors</h3><ul>{"".join(rows)}</ul></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Review: {escape(review.id)}</title>
  <style>{LIST_CSS}</style>
</head>
<body>
  <h1>Review: {escape(review.id)}</h1>
  <p class="subtitle">Canonical edit surface: output/reviews/{escape(review.id)}.json</p>
  <div class="preview-block"><h3>Stem gist</h3><p>{stem}</p></div>
  {"<div class='preview-block'><h3>Stem clues</h3><p>" + clues + "</p></div>" if clues else ""}
  {"<div class='preview-block'><h3>Correct pearl</h3><p>" + escape(review.correct_pearl) + "</p></div>" if review.correct_pearl else ""}
  {distractors}
  {section}
  {cards_html}
</body>
</html>
"""


def write_high_yield_html(reviews: list[QuestionReview], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_high_yield_page(reviews), encoding="utf-8")


def write_item_preview(review: QuestionReview, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_item_preview(review), encoding="utf-8")
