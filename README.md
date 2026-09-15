# anki-bot



Turn board-style question screenshots **and lecture HTML files** into:



1. **Standalone color-coded high-yield HTML lists** — one per lecture topic or qbank run.

2. **Anki cloze cards** in labeled `.apkg` files under `output/ankideck/` — one sentence per card, same five colors on terms.



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

2. Create a virtual environment and install (from your clone of this repo):



```powershell

cd path\to\anki-bot

python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"

```



3. **Add your Gemini API key** — see [Gemini API key](#gemini-api-key-env-file) below (after [Running anki-bot](#running-anki-bot-windows)).



## Running anki-bot (Windows)



Use this checklist **every time** you process content:



1. **VPN (hospital / university)** — Connect VPN *before* running if your network blocks Google APIs. Without VPN you may see DNS errors (`getaddrinfo failed`) or “Could not reach the Gemini API”. Quick test in PowerShell: `Resolve-DnsName generativelanguage.googleapis.com`.

2. **Open a terminal at the repo root** — The folder that contains `.env`, `.venv`, `pyproject.toml`, and `input/`.

3. **Confirm the venv is active** — Prompt shows `(.venv)`, or use [Auto-activate venv in Cursor](#auto-activate-venv-in-cursor) below. If `anki-bot` is not recognized, activate the venv or use `.\.venv\Scripts\anki-bot.exe`.

4. **Run** — Pick a [workflow](#workflows--lecture-html-vs-exam-questions) (lecture HTML or exam PNGs). Examples from repo root:



```powershell

anki-bot process input\infectious-disease.html

anki-bot process input\abp\orthopedic-sports-med

anki-bot process input

```



5. **Confirm `.env`** — `GEMINI_API_KEY` lives in the project-root `.env` file (loaded automatically).



The CLI prints `Output directory: ...` at the start of each run. With default `-o output`, that path is **`<repo>\output`**, even if your shell cwd is nested under `input/` (see [Where outputs go](#where-outputs-go)).



### Three ways to invoke the CLI



| Method | When to use |

|--------|-------------|

| `anki-bot process ...` | Venv active (recommended) |

| `.\.venv\Scripts\anki-bot.exe process ...` | Venv not activated; run from repo root |

| `.\.venv\Scripts\Activate.ps1` then `anki-bot ...` | Manual activation |



### Auto-activate venv in Cursor



This repo includes `.vscode/settings.json`:



- `python.defaultInterpreterPath` → `${workspaceFolder}/.venv/Scripts/python.exe`

- `python.terminal.activateEnvironment` → `true`



Open the **anki-bot** folder as the workspace (not a parent folder), then open a **new** integrated terminal. You should see `(.venv)` without running `Activate.ps1`. If not: Command Palette → **Python: Select Interpreter** → choose `.venv` → new terminal.



External PowerShell windows still need manual activation or the full path to `anki-bot.exe`.



### Troubleshooting



| Symptom | Fix |

|---------|-----|

| `anki-bot is not recognized` | Activate venv, use `.\.venv\Scripts\anki-bot.exe`, or `pip install -e ".[dev]"` |

| `Activate.ps1` blocked | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

| `GEMINI_API_KEY is not set` | Create `.env` from `.env.example` in repo root |

| DNS / `getaddrinfo` / cannot reach Gemini | Enable VPN or another network |

| `output` folder appeared under `input\...` | You used a custom `-o` relative to a nested cwd, or an older version; use repo root, or `-o C:\full\path\to\anki-bot\output`. Default `-o output` now anchors to repo root |



## Workflows — lecture HTML vs exam questions



Choose one path below. Same CLI command; inputs and outputs differ.



**Lecture note:** Your HTML may already use colors from a readout tool. anki-bot extracts **plain text** from HTML and Gemini **rebuilds** pearls in the standard five-color scheme on output files and Anki cards.



| | **Lecture HTML readout** | **Exam question screenshots** |

|--|--------------------------|-------------------------------|

| **You provide** | `.html` / `.htm` (one file or grouped parts) | `.png` / `.jpg` / `.webp` (stem, choices, explanation pages) |

| **Typical source** | Exported lecture notes | UWorld / NBME-style captures |

| **Command (from repo root)** | `anki-bot process input\<file-or-folder>` | Same |

| **Gemini role** | Lecture text → pearls + clozes (15–50 cards by duration) | OCR → stem, distractors, pearls + clozes (1–5 cards) |

| **Review JSON** | `output/reviews/<id>.json` (e.g. `01-adrenal-lecture`) | `output/reviews/<id>.json` (e.g. `12-endocrine`) |

| **Color-coded preview** | `output/reviews/<id>.html` | `output/reviews/<id>.html` |

| **Combined color-coded list** | `output/<short-id>-high-yield.html` | Run: `qbank-abp<N>-high-yield.html`; compiled: `qbank-abp-high-yield.html` |

| **Anki deck** | `output/ankideck/<short-id>.apkg` | Run: `ankideck/qbank-abp<N>.apkg`; **compiled:** `ankideck/qbank-abp.apkg` |

| **Track** | From `input/abp/` or `input/endo/` path | Same |

| **After editing JSON** | `anki-bot build-apkg output\reviews` | Same |



### Workflow A — Lecture HTML



1. Put HTML in `input/` (e.g. `infectious-disease.html` or `01-id-lecture.html` + parts).

2. (Recommended) Add `<meta name="lecture-hours">` and `<meta name="lecture-topic">` in `<head>` — see [Lecture metadata](#lecture-metadata-optional).

3. VPN if needed → venv active → `anki-bot process input\your-lecture.html`.

4. Review `output/reviews/<id>.html`; edit `output/reviews/<id>.json` if needed.

5. Import `output/ankideck/<short-id>.apkg` into Anki (e.g. `infectious-disease.apkg`); open the matching `-high-yield.html` in a browser.



### Workflow B — Exam questions



1. Put PNGs in `input/` with a shared prefix per question, or one subfolder per question — see [Input grouping](#input-grouping).

2. VPN if needed → venv active → `anki-bot process input` (or a subfolder).

3. Per question: `output/reviews/<id>.json` and `output/reviews/<id>.html`.

4. Run pack: `output/ankideck/qbank-abp<N>.apkg`. **Compiled (re-import this):** `output/ankideck/qbank-abp.apkg`.

5. Edit JSON → `anki-bot build-apkg output\reviews`.



**Mixed run:** Short-named lecture `.apkg` files plus per-track qbank run + compiled packs.



**Incremental runs:** Unchanged inputs are skipped; terminal shows **Ran** vs **Ignored**. Use `--force` to reprocess.



**Optional flags (both):**



- `--review-only` — JSON + HTML only; skip `.apkg` until editing is done.

- `--force` — reprocess even when source files are unchanged.

- `build-apkg` — rebuild HTML and `.apkg` from edited JSON without calling Gemini.



## Where outputs go



- **Inputs** stay under `input/` (or whatever path you pass to `process`).

- **All generated files** go under `-o` / `--output` (default: `<repo>/output/`).

- Typical layout:

  - `output/reviews/<id>.json` — canonical edit surface

  - `output/reviews/<id>.html` — color-coded preview per item

  - `output/<short-id>-high-yield.html`, `output/qbank-abp-high-yield.html`, `output/qbank-abp<N>-high-yield.html`

  - `output/ankideck/*.apkg` — all Anki import files (lectures + qbank run + compiled)
  - High-yield HTML stays in `output/` (not in `ankideck/`)

**Migrate nested outputs:** `python scripts/migrate_nested_outputs.py` (from old `input/**/output/` layouts).



Default `-o output` is resolved to the **repository root** (directory containing `pyproject.toml`), not your current working directory, so running `anki-bot process .` from inside `input\abp\<id>` still writes to `<repo>\output`. Custom `-o myfolder` is still relative to the shell cwd.



### Gemini API key (`.env` file)



anki-bot reads your API key from a file named `.env` in the project folder. That file is **not** committed to git (it stays on your machine).



**Step 1 — Get a key from Google**



1. Open [Google AI Studio → API keys](https://aistudio.google.com/apikey).

2. Sign in with your Google account.

3. Click **Create API key** (pick an existing Google Cloud project or create one when prompted).

4. Copy the key — it looks like `AIzaSy...` (a long string). Keep it private.



**Step 2 — Create `.env` from the template**



From the repo root:



```powershell

Copy-Item .env.example .env

```



**Step 3 — Paste your key into `.env`**



```env

GEMINI_API_KEY=AIzaSy_paste_your_actual_key_here

```



Save the file. No quotes around the key.



**Step 4 — Confirm it works**



Follow [Running anki-bot (Windows)](#running-anki-bot-windows) (venv + VPN if needed), then run one real input — for example:



```powershell

anki-bot process input\my-question-folder

```



Tests use a JSON fixture and do not need a key: `pytest`.



If the key is missing or wrong, you will see `GEMINI_API_KEY is not set` or an authentication error from Google.



## Usage



Use an integrated terminal with [auto-venv](#auto-activate-venv-in-cursor), or activate manually. See [Workflows](#workflows--lecture-html-vs-exam-questions) for lecture HTML vs exam PNGs.



Drop files into `input/`, then from repo root:



```powershell

anki-bot process input

```



**Filename pattern (exam PNGs, recommended):**



```text

<number>-<topic>-<part>.png

```



Examples: `12-endocrine-part1.png`, `12-endocrine-explanation.png`. All files sharing the same `<number>-<topic>` prefix are **one question**.



**Lecture HTML pattern:**



```text

<number>-<topic>-lecture.html

```



Review ids for lectures end with `-lecture` (e.g. `01-adrenal-lecture`) so they do not collide with PNG groups for the same topic.



### Lecture metadata (optional)



```html

<meta name="lecture-hours" content="1.5">

<meta name="lecture-topic" content="Orthopedics">

```



Supported duration formats: `1.5`, `1.5h`, `90min`, `1:30`. Aliases: `duration`, `lecture-duration`.



If `lecture-hours` is missing, anki-bot estimates duration from character count (~18,000 chars/hour by default) and warns.



Options:



```powershell

anki-bot process input --review-only

anki-bot process input --max-cards 30

anki-bot build-apkg output\reviews

```



### Model selection



anki-bot **always uses `gemini-3.1-pro-preview`** for accuracy. Use `--model` only as an escape hatch (e.g. `gemini-3.5-flash`).



### Adaptive card budgets



Quality-first: fewer excellent cards beats filling a quota.



| Input | Soft target (prompt) | Hard ceiling |

|-------|----------------------|--------------|

| Board question (PNG group) | **1–5** | 5 |

| Lecture **< 1 hour** | **15–20** | 20 |

| Lecture **≥ 1 hour** | **20–50** | 50 |



`--max-cards N` / `ANKI_BOT_MAX_CARDS` is an optional hard override.



### Input grouping



| Method | Example | Result |

|--------|---------|--------|

| **Numbered filenames** | `12-endocrine-part1.png`, `12-endocrine-part2.png` | One question: `12-endocrine` |

| **Lecture HTML** | `01-adrenal-lecture.html`, `01-adrenal-lecture-part2.html` | One lecture: `01-adrenal-lecture` |

| **Subfolder** | `input/q12/1.png`, `input/q12/2.png` | One question: `q12` |

| **Legacy prefix** | `item_1.png`, `item_2.png` | One question: `item` |



Supports `.png`, `.jpg`, `.jpeg`, `.webp`, `.html`, `.htm`.



### Outputs



See [Where outputs go](#where-outputs-go) and the [workflows table](#workflows--lecture-html-vs-exam-questions). Examples:



- `input/abp/infectious-disease/…` → `output/ankideck/infectious-disease.apkg`, `output/infectious-disease-high-yield.html`

- 12 ABP question groups in one run → `output/ankideck/qbank-abp12.apkg` + `output/ankideck/qbank-abp.apkg`



### Cost awareness



After each Gemini call, anki-bot prints token usage and estimated USD. End of run: totals and a **50-hour projection** from observed $/lecture-hour (Pro rates; Google invoice is source of truth).



## Tests (no API key)



```powershell

pytest

```



## Disclaimer



anki-bot summarizes facts visible in your screenshots and lecture HTML. It is not clinical advice. Verify pearls before studying.

