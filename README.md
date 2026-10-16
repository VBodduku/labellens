# LabelLens

Point your phone at a packaged-food label. LabelLens reads it, checks it against every family member's allergies, diets and health limits, and shows **the exact words on the packet** behind every flag. When it can't read something, it says so instead of guessing.

Every result is one of four states: **Conflict**, **Check this**, **Not listed** or **Unknown** (not detected / can't determine). LabelLens never says "safe" or "healthy".

## How it works

```
phone (frontend/, React PWA)
  │  up to 3 label photos + family profiles + language
  ▼
POST /api/scan (backend/, FastAPI)
  1. quality check → focus (crop to the text, turn it upright, enlarge) → OCR (rapidocr: every word with its position)
  2. Gemini structures the label, citing OCR words
     (fallbacks: backup key → Ollama on this Mac → OCR-only)
  3. alignment: each item is verified / approximate / unverified against the OCR words
  4. self-check: re-reads blurry or inconsistent regions (max 2)
  ▼
engine/ (deterministic rules, no network)
  knowledge base (INS codes, Hindi/Telugu names) → verdict per profile,
  nutrition consistency check, "couldn't read" items
  ▼
backend: AI interpretations for unknown terms (can raise to "Check this", never "Conflict"),
         short summaries in en / hi / te, cache
  ▼
result screen: verdict per family member, tap a flag → zoom to the words on the photo,
               corrections (/api/recheck), questions by text or voice (/api/ask)
```

`shared/` holds the data contract (Python + TypeScript) and the demo label fixtures used by "Try the demo label".

## Requirements (macOS)

- Python **3.12** (`brew install python@3.12`; newer versions break the OCR library)
- Node 22 or newer
- A free Gemini API key from Google AI Studio (a second key from another Google account helps with rate limits)
- Optional: [Ollama](https://ollama.com) with `gemma3:4b` (offline fallback), `cloudflared` (HTTPS link for the phone)

## Setup (once, from the repo root)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r engine/requirements.txt

cp .env.example .env            # then put your key(s) in GEMINI_API_KEY / GEMINI_API_KEY_BACKUP

cd frontend && npm install && cd ..
```

## Run

Three terminals, all starting in the repo root:

```bash
# 1. backend
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
#    check http://localhost:8000/api/health  →  "engine": "real"

# 2. frontend (Vite forwards /api to the backend)
cd frontend && npm run dev       # http://localhost:5173

# 3. HTTPS link for the phone camera
cloudflared tunnel --url http://localhost:5173
```

Open the printed `https://….trycloudflare.com` link on the phone. Keep `VITE_API_BASE_URL` empty in `.env` for this setup; the phone must call the same origin.

Before a demo, scan the demo packets once so every later scan is instant and uses no quota:

```bash
python -m backend.scripts.warm_cache "/path/to/packet_photos"     # one subfolder per packet
```

## Tests

```bash
source .venv/bin/activate
python -m pytest engine/tests backend/tests                      # live Gemini tests: add -m live
cd frontend && npm run build && npm run lint && npm run test
```

## Project layout

| Path | What it is |
|---|---|
| `frontend/` | React + Vite PWA: camera capture, evidence viewer, family verdicts, i18n, voice. See `frontend/README.md`. |
| `backend/` | FastAPI: OCR, Gemini/Ollama structuring, alignment, self-check, agent, summaries, cache. See `backend/README.md`. |
| `engine/` | Deterministic verdict engine, knowledge base, evaluation harness. See `engine/README.md`. |
| `shared/` | Contract types, engine interface, message templates, demo fixtures (`python -m shared.fixtures.build_fixtures`). |
| `docs/` | Product and design specs, translation review list. |

## Accuracy numbers

`engine/eval/` scores real photographed packets (`engine/eval/dataset/README.md`). Copy `engine/eval/reports/metrics.json` to `frontend/public/metrics.json`; the About page shows numbers only for real packets.

## Open items

- Evaluate 10+ real packets and publish the metrics.
- Native-speaker review of Hindi/Telugu text (`docs/TRANSLATION_REVIEW.md`).
- Calibrate camera quality thresholds on the demo phone (`/scan?debug=1`).
- Human review of contested knowledge-base entries (`engine/KB_REVIEW.md`).
- Deployment (Render for the backend via `backend/Dockerfile`, Vercel for the frontend): see `backend/README.md` and `frontend/README.md`.
