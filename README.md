# LabelLens

Point your phone at a packaged-food label. LabelLens reads it, checks it against every family member's allergies, diets and health limits, and shows **the exact words on the packet** behind every flag. When it can't read something, it says so instead of guessing.

Every result is one of four states: **Conflict**, **Check this**, **Not listed** or **Unknown** (not detected / can't determine). LabelLens never says "safe" or "healthy".

**Links:** live app: _add the Vercel URL_ · backend: _add the Render URL_ · demo video: _add the link_ · deployment: [`docs/DEPLOY_VERCEL.md`](docs/DEPLOY_VERCEL.md)

## The problem

Indian food labels are complete but hard to use in a shop aisle:
- Allergens hide behind other names (whey, casein, INS 322) and codes (INS 120, INS 441).
- One shopper buys for a child with a peanut allergy, a diabetic parent and a Jain adult.
- A blurry photo is not proof that an ingredient is absent, but most scanner apps treat "didn't see it" as "not there".

LabelLens checks one photo for the whole family, ties every flag to the words on the photo, and is honest about what it could not read. Full problem statement: [`docs/00_MASTER_SPEC.md`](docs/00_MASTER_SPEC.md).

## Features

| Feature | What it does |
|---|---|
| **Evidence on the photo** | Every Conflict or Check this quotes the label text. Tap it and the photo zooms to those words. Text that can't be located says so. |
| **Family verdicts** | One scan gives a verdict per person: allergies (15 allergen groups), diets (vegetarian, vegan, Jain, no onion/garlic…) and health limits (sugar, sodium, saturated fat). |
| **Honest unknowns** | "Not listed" only when the whole ingredient list was read. Otherwise the result is Unknown, and the "Couldn't read" tab offers **Retake this area** for the exact region. |
| **Indian label knowledge** | 263 knowledge-base entries: INS/E codes, Hindi and Telugu names, hidden dairy and sugars, Jain rules, the green/brown veg mark. |
| **Self-checking reading** | The AI's numbers must match the printed OCR text and sit on their own row. Calories are cross-checked against protein, carbs and fat. Unclear regions are re-read. |
| **Contradictions** | When two readings disagree (veg mark vs an ingredient, "free from" vs the list, a claim vs the table, the AI vs the print, two photos), both sides are shown. The stricter side is used until the user checks the pack. |
| **Check the pack** | The user can settle an ambiguous ingredient ("does natural flavours contain onion?") or a contradiction. The answer is saved and every verdict is rechecked, labelled "Checked by you". |
| **Corrections** | Edit any ingredient or nutrient value; verdicts update in under a second (engine only, no AI). |
| **Compare two products** | Scan product A, then B: each person's verdicts side by side, per-100 g nutrition and the differences that matter. |
| **Ask the label** | Questions by text or voice ("Is this okay for Thatha?", "Is it vegan?", "How much sugar per serving?"), answered only from engine results and label text. Medical questions are refused. |
| **Three languages** | English, Hindi and Telugu screens, summaries and read-aloud. |
| **Works when AI is down** | Gemini → backup key → local Ollama → basic text reading (OCR only), which says so and asks the user to check. The demo label works with no backend at all. |
| **Installable app** | A PWA for Android, iOS and desktop, with a live camera, quality hints (blur, glare, dark) and up to 3 photos per scan. |

## How it works

```
phone (frontend/, React PWA)
  │  up to 3 label photos + family profiles + language
  ▼
POST /api/scan (backend/, FastAPI)
  1. quality check → focus (crop to the text, turn it upright, enlarge) → OCR (rapidocr: every word with its position)
  2. Gemini structures the label, citing OCR words
     (fallbacks: backup key → Ollama on this Mac → OCR-only)
  3. alignment: each item is verified / approximate / unverified against the OCR words;
     numbers must match the print and sit on their own row; a green veg mark must be green on the photo
  4. self-check: re-reads blurry or inconsistent regions (max 2)
  ▼
engine/ (deterministic rules, no network)
  knowledge base (INS codes, Hindi/Telugu names) → verdict per profile,
  nutrition consistency check, contradictions, "couldn't read" items
  ▼
backend: AI interpretations for unknown terms (can raise to "Check this", never "Conflict"),
         short summaries in en / hi / te, cache
  ▼
result screen: verdict per family member, tap a flag → zoom to the words on the photo,
               corrections and pack checks (/api/recheck), questions by text or voice (/api/ask), compare
```

The AI only reads the label. **Every verdict comes from the deterministic rules engine** ([`engine/`](engine/README.md)), which is unit-tested row by row against the verdict table in the master spec (§9).

`shared/` holds the data contract (Python + TypeScript) and the demo label fixtures used by "Try the demo label".

## Requirements

- Python **3.12** (`brew install python@3.12` on macOS; newer versions break the OCR library)
- Node 22 or newer
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/) (a second key from another account helps with rate limits)
- Optional: [Ollama](https://ollama.com) with `gemma3:4b` (offline fallback), `cloudflared` (HTTPS link for the phone camera)

Main libraries (all free and open source): FastAPI, Pydantic, RapidOCR (onnxruntime), OpenCV, Pillow, rapidfuzz, google-genai, httpx; React 18, Vite, TypeScript, Tailwind CSS, Zustand, react-i18next, Motion, three.js. Full lists: `backend/requirements.txt`, `engine/requirements.txt`, `frontend/package.json`.

## Setup (once, from the repo root)

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt -r engine/requirements.txt

cp .env.example .env               # then put your key(s) in GEMINI_API_KEY / GEMINI_API_KEY_BACKUP

cd frontend && npm install && cd ..
```

## Configuration (`.env`)

| Variable | Default | What it does |
|---|---|---|
| `GEMINI_API_KEY` | (empty) | Google AI Studio key. Without it, scans use Ollama or basic text reading. |
| `GEMINI_API_KEY_BACKUP` | (empty) | Second key, used when the first is rate limited or refused. |
| `GEMINI_MODEL` | `gemini-flash-latest` | Main model. |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.5-flash,gemini-flash-lite-latest,…` | Tried in order on the same key when the main model is overloaded or out of quota. |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `http://localhost:11434`, `gemma3:4b` | Local vision model used when Gemini is unavailable. |
| `LLM_TIMEOUT_S` | `30` | Timeout per AI call. A whole scan is capped at 45 s. |
| `ENGINE_MODE` | `real` | `real` = `engine/`; `stub` = a naive stand-in for tests. |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Frontend origins allowed to call the backend (add the Vercel URL when deployed). |
| `CACHE_DIR` | `.cache` | Disk cache of readings, keyed by photo bytes, so repeat scans are instant and free. |
| `MAX_IMAGES`, `MAX_IMAGE_MB` | `3`, `8` | Upload limits. |
| `OCR_WORKERS` | `3` | Parallel OCR runs; `1` on small hosts (Render free: 512 MB). |
| `VITE_API_BASE_URL` | (empty) | Empty locally (Vite forwards `/api`). For a deployed frontend: the backend URL. |
| `API_PROXY_TARGET` | `http://localhost:8000` | Where the dev server forwards `/api`. |
| `VITE_USE_MOCKS` | `false` | `true` = the frontend uses the bundled fixtures, no backend needed. |

## Run

Three terminals, all starting in the repo root:

```bash
# 1. backend
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
#    check http://localhost:8000/api/health  →  "engine_mode": "real", "gemini": true

# 2. frontend (Vite forwards /api to the backend)
cd frontend && npm run dev       # http://localhost:5173

# 3. HTTPS link for the phone camera
cloudflared tunnel --url http://localhost:5173
```

Open the printed `https://….trycloudflare.com` link on the phone. Keep `VITE_API_BASE_URL` empty in `.env` for this setup, so the phone calls the same origin.

No camera or backend? Click **Try the demo label** on the home page.

Before a demo, scan the demo packets once, so every later scan is instant and uses no quota:

```bash
python -m backend.scripts.warm_cache "/path/to/packet_photos"     # one subfolder per packet
```

## Tests and evaluation

```bash
source .venv/bin/activate
python -m pytest engine/tests backend/tests                      # 948 tests; live Gemini tests: add -m live
cd frontend && npm run build && npm run lint && npm run test     # 161 tests
```

| Document | Contents |
|---|---|
| [`docs/TEST_RESULTS.md`](docs/TEST_RESULTS.md) | Three acceptance tests (clear label, partly unreadable label, conflicting or incomplete information). Each was run 3 times with fresh AI readings, with expected vs actual, pass/fail, evidence, false positives, misses and the fixes made. Raw evidence: [`docs/test_evidence/`](docs/test_evidence). |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | Test coverage by area, the synthetic pipeline check, limitations, and how evidence traceability was improved. |
| `engine/eval/` | Accuracy harness for real photographed packets ([`engine/eval/dataset/README.md`](engine/eval/dataset/README.md)). Real-packet numbers are still pending. |

Re-run the acceptance tests against a running backend:

```bash
python -m backend.scripts.acceptance_tests "/path/to/photos" --url http://localhost:8000
```

Test photos are not committed (they are product packaging). The runner builds the blurred and covered versions itself from one clear photo.

## Project layout

| Path | What it is |
|---|---|
| `frontend/` | React + Vite PWA: camera capture, evidence viewer, family verdicts, comparison, i18n, voice. See [`frontend/README.md`](frontend/README.md). |
| `backend/` | FastAPI: OCR, Gemini/Ollama structuring, alignment, self-check, text-only reader, question answering, summaries, cache. See [`backend/README.md`](backend/README.md). |
| `engine/` | Deterministic verdict engine, knowledge base, contradictions, evaluation harness. See [`engine/README.md`](engine/README.md). |
| `shared/` | Data contract (Python + TypeScript), engine interface, message templates, demo fixtures (`python -m shared.fixtures.build_fixtures`). |
| `docs/` | Specs, test results, evaluation, demo script, jury guide, deployment guide, translation review list. |

Design decisions are recorded one line each in `backend/DECISIONS.md`, `engine/DECISIONS.md` and `frontend/DECISIONS.md`.

## Limitations

- **Accuracy on real packets is not yet measured.** The acceptance tests use one real label (plus edited versions) and the demo label. The accuracy harness is ready, but 10+ hand-labelled packets have not been scored.
- **AI readings vary from run to run.** The checks in alignment and the engine catch the failures found so far (invented veg mark, numbers moved between rows, missed allergen statement), but a model can fail in new ways. Hence the four honest states and "check the pack".
- **Hindi and Telugu print** is read only by the AI; OCR reads Latin script. Evidence for those words is the AI's approximate box. All hi/te text still needs native-speaker review ([`docs/TRANSLATION_REVIEW.md`](docs/TRANSLATION_REVIEW.md)).
- **Basic reading (no AI)** reads ingredients and statements by keyword rules. It never says "Not listed" from the list, uses nutrition numbers only when the label corroborates them, and can stop early on tightly packed two-column layouts.
- **Knowledge base:** 40 entries await expert review ([`engine/KB_REVIEW.md`](engine/KB_REVIEW.md)), for example contested additive sources and dried ginger/turmeric for Jain diets.
- **Speed:** fresh scans take about 15–40 s on Gemini's free tier (target 8 s). Repeat scans of the same photo are instant (cache).
- **Free hosting:** Render's free tier sleeps after 15 minutes idle (about a minute to wake) and has 512 MB of memory, so OCR runs one photo at a time.
- Camera quality thresholds (blur, glare) are not calibrated on real phones yet; barcode and QR areas can trigger a glare warning.

## Future improvements

- Score 10–15 real packets and publish the accuracy numbers on the About page.
- Native-speaker review of Hindi/Telugu; OCR models for Devanagari and Telugu script so that evidence is verified.
- Split OCR-glued words before ingredient matching ("EXTRACTANDACIDITY"); read tightly packed two-column ingredient lists.
- Calibrate camera and glare thresholds on the demo phone; ignore barcode and QR areas.
- Offer the diet check ("Is it vegan?") to the Gemini answerer too, not only the no-AI answerer.
- A Capacitor build for an Android APK.

## AI and tools disclosure

LabelLens was built with substantial AI assistance. In detail:

**AI coding assistants (development)**
- **Claude Code** (Anthropic): wrote most of the code in all four folders, the tests and the documentation, working from the specs in `docs/`. 91 commits carry its `Co-Authored-By: Claude` line. Its instructions are in [`CLAUDE.md`](CLAUDE.md).
- **Codex** (OpenAI): used for the rules engine, knowledge base and evaluation harness (`engine/`, Part 3 of the specs). Its instructions are in [`AGENTS.md`](AGENTS.md).
- The team wrote the specs and product decisions, chose the persona and demo, photographed the test packets, reviewed and merged the code, and ran the integration and acceptance testing.

**AI in the running app (runtime)**
- **Google Gemini API** (free tier, `google-genai` SDK): reads the label photo into structured data, interprets ingredients the knowledge base doesn't know (capped at "Check this"), writes the short summaries and answers questions with tools. It never decides a verdict.
- **Ollama with Gemma 3 (4B)**: optional local fallback when Gemini is unavailable.
- **RapidOCR** (open-source models on onnxruntime): word-level text recognition on the device running the backend.

**Not AI:** the verdicts (the deterministic engine in `engine/`), the knowledge base (hand-written JSON with sources and review notes), and the hi/te state words and templates (fixed strings, marked for native-speaker review).

**Team and contributions** (commit authors: Vishwak, Vidur-2007, VBodduku)

| Member | Contributions |
|---|---|
| _name_ | _fill in: parts owned, decisions made, testing done_ |
| _name_ | _fill in_ |
| _name_ | _fill in_ |

The jury guide ([`docs/JURY_GUIDE.md`](docs/JURY_GUIDE.md)) explains the architecture and the key technical decisions, so that every member can present them.
