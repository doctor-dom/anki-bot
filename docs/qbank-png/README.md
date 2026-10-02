# Qbank PNG processing and compilation

Agent reference for turning question screenshots into review JSON, then into the three qbank packs: **all-track**, **topic**, and **folder**. Lecture HTML is a separate path; do not fold it into these packs.

Canonical code: `anki_bot/discover.py`, `anki_bot/image_ocr.py`, `anki_bot/gemini_review.py`, `anki_bot/pipeline.py`, `anki_bot/outputs.py`, `anki_bot/media.py`, `anki_bot/html_render.py`, `anki_bot/apkg.py`. Prompt: `prompts/tutor.md`.

## Invariants

- One discovered group is one question. A batch folder such as `abp-qbank-10` is not a question id.
- The only per-question artifact is `output/<track>/reviews/<id>.json`. There is no per-question HTML.
- Every `process`, `run`, and `build-apkg` rebuilds **all** qbank packs from **every** question review JSON under `output/`, including questions skipped this run. `this_run_reviews` is ignored in `packs_for_reviews`.
- Unchanged sources are skipped before Gemini (fingerprint is size + sha256 + basename). Packs still include those reviews.
- Facts in pearls and clozes come only from the screenshot (or its OCR text). `prompts/tutor.md` is the grounding rule.
- Legacy names are deleted on each pack write: `output/<track>/reviews/<id>.html`, `output/<track>/qbank-*-high-yield.html`, and `output/<track>/ankideck/qbank-*.apkg`. Do not recreate `qbank-<track>` deliverables.

## Input layout

Track is the first folder under `input/`. Files sitting directly in `input/` use track `misc`.

```text
input/abp/abp-qbank-10/12-endocrine-part1.png
input/abp/abp-qbank-10/12-endocrine-explanation.png
input/abp/abp-qbank-10/12-endocrine-cxr.png
```

That folder is one **folder** pack (`abp-qbank-10`). The shared prefix `12-endocrine` is one question. `endocrine` is the **topic**. The track `abp` is the **all-abp** pack.

### How PNGs become one question

`discover_content` groups images in a directory when any file matches a numbered or legacy stem (or when the directory holds a single image).

| Pattern | Example | Group id |
|---------|---------|----------|
| Numbered topic | `12-endocrine-part1.png`, `12-endocrine-explanation.png` | `12-endocrine` |
| Legacy prefix | `item_1.png`, `item_2.png` | `item` |
| Plain subfolder | `input/abp/q12/1.png`, `2.png` (no numbered/legacy stems) | `q12` |

Numbered stems split on `-` at most twice: `<number>-<topic>-<rest>`. `<number>` and `<topic>` must be a single token each (`[A-Za-z0-9]+` and a token that may contain spaces). Anything after the second hyphen is the part suffix and is **not** part of the id. `10-t1dm-honeymoon-part1.png` groups as `10-t1dm`, not `10-t1dm-honeymoon`. Keep PNG topics hyphen-free. PDF names are different: `10 - T1DM honeymoon.pdf` becomes `10-t1dm-honeymoon`.

Supported image suffixes: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`.

If the same id appears in more than one folder, each id is prefixed with the parent folder slug (`abp-qbank-10-12-endocrine`). A prefixed id no longer starts with a digit, so topic parsing falls through to `other` unless `review.topic` is set.

## Processing one PNG question

`anki-bot process <path>` and `anki-bot run` both call `process_path`. `run` discovers `input/` (plus optional Drive input).

1. Discover groups. Skip a group when `output/<track>/reviews/<id>.json` already matches the source fingerprint, unless `--force`.
2. `prepare_png_question_input` (`ANKI_BOT_PNG_MODE`, default `auto`).
3. `review_question` runs Tesseract for archival (`output/<track>/ocr/`), then sends **PNG image parts** to Gemini in `auto` mode (not OCR text). Card budget is 1–5 (hard max 5). `ANKI_BOT_BULK_QBANK=1` caps at 3.
4. `filter_valid_cards`, attach fingerprint, set `track` from the group.
5. Write `output/<track>/reviews/<id>.json`. Copy kept images into `output/<track>/media/`.
6. Load every review JSON and write the packs below.

`review.topic` is not filled from the filename. Topic packs derive the key from the id unless something else set `topic`.

### PNG mode (`ANKI_BOT_PNG_MODE`)

| Mode | Behavior |
|------|----------|
| `vision` | Send every image. No OCR. |
| `text` | OCR only. Missing Tesseract or empty OCR raises. |
| `auto` | OCR every page into `output/<track>/ocr/`; Gemini always receives the PNG bytes (Flash for text screenshots, Pro when a figure page is present). |

`prepare_png_question_input` still classifies pages for logging and hybrid edge cases; `auto` does **not** substitute OCR text for Gemini.

`auto` per image (OCR archive + figure detection):

- OCR failure, or OCR shorter than 80 characters: that page goes to vision.
- Figure-like page (filename matches `cxr`, `xray`, `ecg`, `rash`, `figure`, `scan`, `graph`, …, or mean RGB stddev ≥ `ANKI_BOT_FIGURE_COLOR_VARIANCE`, default 55) **and** (sparse OCR or a figure-like filename): that page stays on vision. Any partial OCR text is still included, labeled `(OCR partial)`.
- Otherwise the page is text: `=== <filename> ===`.

After the pages are combined:

- Empty text → full vision of every image.
- Text that does not look like an MCQ (`looks_like_mcq`: length plus `CORRECT` / `EXPLANATION` or an `A–E` choice marker) → full vision, unless `ANKI_BOT_PNG_KEEP_OCR=1`, which keeps the OCR text and sends vision only for figure pages.
- MCQ-like text → OCR text, plus vision only for the figure/sparse pages.

Missing Tesseract in `auto` warns once and uses full vision. Set `ANKI_BOT_TESSERACT_CMD` when `tesseract.exe` is not on `PATH`.

### Model (`GEMINI_MODEL=auto`)

| Prepared input | Model |
|----------------|-------|
| `PNG_MODE=text`, OCR text only | Flash Lite |
| `PNG_MODE=text`, OCR plus figure vision page(s) | Flash Lite or Pro |
| `PNG_MODE=auto` or `vision`, text screenshots | Flash |
| `PNG_MODE=auto` or `vision`, any figure page | Pro |

`ANKI_BOT_ESCALATE_PRO=1` retries on Pro with `force_vision` when item confidence is below 0.85 or a warning mentions a missing explanation or an ambiguous correct answer. Vision uploads are downscaled to `ANKI_BOT_MAX_IMAGE_SIDE` (default 1600).

## Compilation: all-track, topic, folder

`packs_for_reviews` emits one set of packs per track that has `kind: question` reviews. A track with questions always gets the all-track pack, one topic pack per board category that has questions, and one folder pack per distinct input folder key. Questions with no folder key (files directly under `input/<track>/`) appear in all-track and topic packs only.

Sort inside every qbank pack: fine topic key, then the leading number in the id, then id. Ids without a leading number sort last. The HTML heading for a missing fine topic is `Other`.

### All-track (`PackKind.QBANK_ALL`)

Every question in the track. For track `abp` the label is `all-abp`.

| | Path |
|--|------|
| HTML | `output/abp/all-abp-high-yield.html` |
| Anki | `output/abp/ankideck/all-abp.apkg` |
| Deck name | `HUB::all-abp` |

HTML is grouped by topic (`group_by_topic=True`) and includes figures.

### Topic (`PackKind.QBANK_TOPIC`)

Questions in one pediatric board category. Filename topics are still parsed as before (`12-endocrine` → `endocrine`, `10-t1dm-honeymoon` → `t1dm-honeymoon`, or `review.topic` when set) and then mapped onto these buckets:

1. Adolescent Medicine + STI + Sexual Health + Behavioral Health + Substance Abuse (`01-adolescent-behavioral`)
2. Allergy + Immunology + Hematology + Oncology + Rheumatology (`02-allergy-heme-onc-rheum`)
3. Cardiology + Pulmonology (`03-cardiology-pulmonology`)
4. Dermatology (`04-dermatology`)
5. Emergency Medicine + Orthopedics + Musculoskeletal + Ophthalmology + ENT (`05-emergency-msk-ophtho-ent`)
6. Endocrinology + Metabolic Disorders + Genetics (`06-endocrinology-metabolic-genetics`)
7. Gastroenterology (`07-gastroenterology`)
8. Preventative Pediatrics + Growth + Development + Vaccines + Nutrition (`08-preventative-pediatrics`)
9. Infectious Disease (`09-infectious-disease`)
10. Neonatology (`10-neonatology`)
11. Nephrology (`11-nephrology`)
12. Neurology (`12-neurology`)

Unmatched names land in `other`. A longer alias wins when a name could fit two buckets (`growth-hormone` → endocrinology, `growth` → preventative pediatrics).

| | Path |
|--|------|
| HTML | `output/abp/topics/06-endocrinology-metabolic-genetics-high-yield.html` |
| Anki | `output/abp/ankideck/06-endocrinology-metabolic-genetics.apkg` |
| Deck name | `HUB::abp::Endocrinology + Metabolic Disorders + Genetics` |

HTML is grouped by the original filename topic (`group_by_topic=True`) and includes figures. Topic `.apkg` files share `output/<track>/ankideck/` with the all-track deck and with lecture decks. A rebuild deletes topic HTML and track decks that the current packs no longer emit, so old narrow files such as `endocrine.apkg` do not stay in Drive.

### Folder (`PackKind.QBANK_FOLDER`)

Questions from one input directory under the track. The folder is the batch you dropped (for example `abp-qbank-10`), not the topic.

Folder key from `source_fingerprint[].relpath` (posix path relative to the input root):

1. Drop the filename.
2. Drop a leading path segment equal to the track (`abp/abp-qbank-10/12-endocrine.png` → `abp-qbank-10`).
3. Keep nested segments (`abp/batch/week2/file.png` → `batch/week2`).
4. No remaining segments → no folder pack for that review.

If no fingerprint relpath matches, the parent directory name of `source_images` / `source_pdfs` / `source_html` is used, skipping `input`, `screenshots`, `images`, `qbank-html`, and the track name itself.

Label is the slug of the **last** path segment. Nested key `batch/week2`:

| | Path |
|--|------|
| HTML | `output/abp/batch/week2/week2-high-yield.html` |
| Anki | `output/abp/batch/week2/ankideck/week2.apkg` |
| Deck name | `HUB::abp::batch::week2` |

Flat key `abp-qbank-10`:

| | Path |
|--|------|
| HTML | `output/abp/abp-qbank-10/abp-qbank-10-high-yield.html` |
| Anki | `output/abp/abp-qbank-10/ankideck/abp-qbank-10.apkg` |
| Deck name | `HUB::abp::abp-qbank-10` |

Folder HTML is grouped by topic and includes figures. The same question is in three decks: `all-abp`, its topic deck, and its folder deck. Importing more than one of those into the same Anki profile duplicates notes; they are alternate slices, not a hierarchy Anki merges.

## Figures

Images are copied once to `output/<track>/media/<review-id>-<index>.<ext>`.

`filter_qbank_image_paths` drops stems matching `explanation`, `explain`, `answer`, `stats`, `overview`, or `correct answer` so explanation screenshots are not pasted onto cards. If every image matches, they are all kept.

The stem cloze (or the first card) gets `<img src="<basename>">` in Extra. The `.apkg` embeds those files. HTML uses `media/<basename>` relative to the HTML file, except files whose parent directory is `reviews`, which use `../media/`. Topic HTML lives in `topics/` and folder HTML lives in the batch folder, so those `media/` links do not resolve to `output/<track>/media/`. Anki import does not depend on that relative URL.

## Rebuild without Gemini

When a question is processed from PNGs, local OCR runs before Gemini. The combined text is written to `output/<track>/ocr/<id>.txt` (plain text) and `output/<track>/ocr/<id>.json` (text plus `used_ocr`, vision page paths, warnings). The review JSON field `source_ocr` is set to `ocr/<id>.json` so edits to `reviews/<id>.json` can reopen the original OCR.

Edit pearls or cards in `output/<track>/reviews/<id>.json`, then:

```powershell
anki-bot build-apkg output
```

or:

```powershell
python scripts/rebuild_output_packs.py output
```

Both call `build_from_reviews`, which rewrites every pack from the JSON on disk. `--review-only` on `process` still writes HTML and skips `.apkg`.

## What not to change by accident

- Do not key packs off the old `qbank-<track>` or `qbank-<track><n>` filenames. `cleanup_legacy_qbank_artifacts` removes them.
- Do not treat the batch folder name as the topic, or the topic as the folder. `endocrine.apkg` and `abp-qbank-10.apkg` answer different questions.
- Do not scope pack rebuilds to the current run. A new PNG must show up inside the existing `all-<track>.apkg` together with older reviews.
- Do not write a review HTML beside the JSON. The edit surface is the JSON.
- PNG topic tokens are the second hyphen segment only. Widening that parse changes both grouping and topic packs.

## Tests

```powershell
pytest tests/test_outputs.py tests/test_image_ocr.py tests/test_media.py tests/test_pipeline_run.py tests/test_discover.py
```

`tests/test_outputs.py::test_qbank_packs_all_topic_folder` is the pack contract: id `12-endocrine`, fingerprint relpath `abp-qbank-10/12-endocrine.png` → topic `endocrine`, folder `abp-qbank-10`, and exactly the three pack kinds.
