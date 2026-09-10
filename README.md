# anki-bot

Turn board-style question screenshots **and lecture HTML files** into:

1. **Standalone color-coded high-yield HTML lists** — one per lecture topic or qbank run.
2. **Anki cloze cards** in labeled `.apkg` files — one sentence per card, same five colors on terms.

Facts are extracted **only from what appears in your PNGs or lecture HTML**. Edit `output/reviews/*.json` to fix pearls, then rebuild.

## Color legend

| Category | Color | CSS class |
|----------|-------|-----------|
| Disease / topic | Black | `hy-topic` |
| Signs, symptoms, side effects, negative associations | Red | `hy-neg` |
| Next-best diagnosis / testing | Blue | `hy-dx` |
| Treatment / positive associations | Green | `hy-tx` |
| Distinctions vs other topics | Purple | `hy-diff` |

## Setup

1. Install Python 3.12+ ([python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12`).
2. Create a virtual environment and install:

```powershell
cd C:\Users\dfili\HUB-projects\anki-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

3. **Add your Gemini API key** (see below).

### Gemini API key (`.env` file)

anki-bot reads your API key from a file named `.env` in the project folder. That file is **not** committed to git (it stays on your machine).

**Step 1 — Get a key from Google**

1. Open [Google AI Studio → API keys](https://aistudio.google.com/apikey).
2. Sign in with your Google account.
3. Click **Create API key** (pick an existing Google Cloud project or create one when prompted).
4. Copy the key — it looks like `AIzaSy...` (a long string). Keep it private.

**Step 2 — Create `.env` from the template**

In PowerShell, from the project folder:

```powershell
cd C:\Users\dfili\HUB-projects\anki-bot
Copy-Item .env.example .env
```

That creates a new file `.env` next to `.env.example`.

**Step 3 — Paste your key into `.env`**

Open `.env` in Cursor (or Notepad) and replace the placeholder:

```env
GEMINI_API_KEY=AIzaSy_paste_your_actual_key_here
```

Save the file. No quotes around the key.

**Step 4 — Confirm it works**

With the venv activated, run a real folder of screenshots (not `pytest` — tests use a fixture and do not need a key):

```powershell
anki-bot process input\my-question-folder
```

If the key is missing or wrong, you will see an error like `GEMINI_API_KEY is not set` or an authentication error from Google.

## Usage

Drop screenshots into `input/` using this filename pattern, then:

```powershell
anki-bot process input
```

**Filename pattern (recommended):**

```text
<number>-<topic>-<part>.png
```

Examples:

```text
12-endocrine-part1.png
12-endocrine-part2.png
12-endocrine-explanation.png
13-cardio-image1.png
```

All files sharing the same `<number>-<topic>` prefix are treated as **one question** (sorted by filename). The part suffix can be anything: `part1`, `image-2`, `explanation`, etc.

You can still use **one subfolder per question** if you prefer; that also works.

**Lecture HTML pattern:**

```text
<number>-<topic>-lecture.html
```

Examples:

```text
01-adrenal-lecture.html
01-adrenal-lecture-part2.html
02-thyroid-lecture.html
```

Lecture files are grouped like screenshots, but review ids end with `-lecture` (e.g. `01-adrenal-lecture`) so they do not collide with question screenshots for the same topic.

### Lecture metadata (optional)

Add these tags in the HTML `<head>` for accurate card budgets and output names:

```html
<meta name="lecture-hours" content="1.5">
<meta name="lecture-topic" content="Orthopedics">
```

Supported duration formats: `1.5`, `1.5h`, `90min`, `1:30`. Aliases: `duration`, `lecture-duration`.

If `lecture-hours` is missing, anki-bot estimates duration from character count (~18,000 chars/hour by default) and warns.

Options:

```powershell
anki-bot process input --review-only              # JSON + HTML only, no .apkg
anki-bot process input --max-cards 30             # optional hard override
anki-bot build-apkg output\reviews                  # after editing JSON
```

### Model selection

anki-bot **always uses `gemini-3.1-pro-preview`** for accuracy (OCR and teaching-point extraction). Cost is accepted in exchange for quality.

Use `--model` only as an escape hatch:

```powershell
anki-bot process input --model gemini-3.5-flash
```

### Adaptive card budgets

Quality-first: fewer excellent cards beats filling a quota.

| Input | Soft target (prompt) | Hard ceiling |
|-------|----------------------|--------------|
| Board question (PNG group) | **1–5** | 5 |
| Lecture **< 1 hour** | **15–20** | 20 |
| Lecture **≥ 1 hour** | **20–50** | 50 |

`--max-cards N` / `ANKI_BOT_MAX_CARDS` is an optional hard override. If omitted, the table applies.

### Input grouping

| Method | Example | Result |
|--------|---------|--------|
| **Numbered filenames** (default) | `12-endocrine-part1.png`, `12-endocrine-part2.png` | One question: `12-endocrine` |
| **Lecture HTML** | `01-adrenal-lecture.html`, `01-adrenal-lecture-part2.html` | One lecture: `01-adrenal-lecture` |
| **Subfolder** | `input/q12/1.png`, `input/q12/2.png` | One question: `q12` |
| **Legacy prefix** | `item_1.png`, `item_2.png` | One question: `item` |

Supports `.png`, `.jpg`, `.jpeg`, `.webp`, `.html`, `.htm`.

### Outputs

| Input | Files | Anki deck name |
|-------|--------|----------------|
| One lecture | `output/reviews/<id>.json`, `output/<topic>-high-yield.html`, `output/<topic>.apkg` | `HUB::<topic>` |
| N board questions in a run | `output/qbank{N}-high-yield.html`, `output/qbank{N}.apkg` | `HUB::qbank{N}` |

Examples:

- `01-ortho-lecture.html` + meta topic Orthopedics → `output/orthopedics.apkg`, `output/orthopedics-high-yield.html`
- 12 PNG question groups → `output/qbank12.apkg`, `output/qbank12-high-yield.html`

A mixed `input/` run writes **one pack per lecture** plus **one qbank pack** for all questions. Per-item JSON stays under `output/reviews/`.

| File | Purpose |
|------|---------|
| `output/reviews/<id>.json` | Canonical editable review (includes `card_budget`, `usage`) |
| `output/reviews/<id>.html` | Preview for pearl-fixing |
| `output/<topic>-high-yield.html` or `output/qbank{N}-high-yield.html` | Standalone high-yield list |
| `output/<topic>.apkg` or `output/qbank{N}.apkg` | Import into Anki (File → Import) |

### Cost awareness

After each Gemini call, anki-bot prints token usage and an estimated USD cost. At the end of a run it shows totals and a **50-hour projection** based on observed $/lecture-hour.

Example calibration: a 1.5 hr lecture at ~8,200 in + 4,100 out tokens ≈ **$0.066** → **~$0.044/hr** → **50 hours ≈ $2.20** on Pro rates. Your Google invoice is the source of truth.

## Tests (no API key)

```powershell
pytest
```

Uses a JSON fixture instead of Gemini.

## Disclaimer

anki-bot summarizes facts visible in your screenshots. It is not clinical advice. Verify pearls before studying.
