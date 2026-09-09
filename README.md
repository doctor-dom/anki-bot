# anki-bot

Turn board-style question screenshots into:

1. A **standalone color-coded high-yield HTML list** (`output/high-yield.html`) — open in a browser, not imported into Anki.
2. **Anki cloze cards** in `output/anki-bot.apkg` — one sentence per card, same five colors on terms.

Facts are extracted **only from what appears in your PNGs**. Edit `output/reviews/*.json` to fix pearls, then rebuild.

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

Options:

```powershell
anki-bot process input --review-only              # JSON + HTML only, no .apkg
anki-bot process input --model gemini-2.5-pro       # force Pro for every question
anki-bot process input --model gemini-2.5-flash     # force Flash
anki-bot build-apkg output\reviews                  # after editing JSON
```

### Auto model selection (default)

`GEMINI_MODEL=auto` in `.env` (the default) uses **Flash** for simple screenshots and upgrades to **Pro** when local image analysis suggests a harder item:

- **3+ screenshots** in one question (multi-page stem + explanation)
- **High resolution** (long side ≥ 1800 px or ≥ 1.8 MP)
- **Large files** (≥ 800 KB — often dense UI captures)
- **Chart/graph-like layouts** (high edge density from tables, graphs, or busy text)
- **Color-rich diagrams**

The chosen model is printed during processing and recorded in the review JSON `warnings` field.

Force a model when you want to skip auto selection:

```powershell
anki-bot process input --model gemini-2.5-flash
anki-bot process input --model gemini-2.5-pro
```

### Input grouping

| Method | Example | Result |
|--------|---------|--------|
| **Numbered filenames** (default) | `12-endocrine-part1.png`, `12-endocrine-part2.png` | One question: `12-endocrine` |
| **Subfolder** | `input/q12/1.png`, `input/q12/2.png` | One question: `q12` |
| **Legacy prefix** | `item_1.png`, `item_2.png` | One question: `item` |

Supports `.png`, `.jpg`, `.jpeg`, `.webp`.

### Outputs

| File | Purpose |
|------|---------|
| `output/reviews/<id>.json` | Canonical editable review |
| `output/reviews/<id>.html` | Preview for pearl-fixing |
| `output/high-yield.html` | Running standalone high-yield list |
| `output/anki-bot.apkg` | Import into Anki (File → Import) |

## Tests (no API key)

```powershell
pytest
```

Uses a JSON fixture instead of Gemini.

## Disclaimer

anki-bot summarizes facts visible in your screenshots. It is not clinical advice. Verify pearls before studying.
