# LabelLens backend (Part 2)

FastAPI service that turns label photos into an evidence-linked `ScanResult` (see `docs/PART2_BACKEND_SPEC.md`).

## Run (from the repo root)
```bash
python3.12 -m venv .venv            # Python 3.12: rapidocr-onnxruntime does not support 3.13
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env                # ENGINE_MODE=stub until the engine is merged
.venv/bin/uvicorn backend.app.main:app --reload --port 8000
.venv/bin/python -m pytest backend/tests
```
(Windows: `.venv\Scripts\python` instead of `.venv/bin/python`.)

## Scripts
- `python -m backend.scripts.make_test_label [out.png]`: draws the fixture's OCR tokens onto a PNG at their boxes (default `.cache/test_label.png`).
- `python -m backend.scripts.ocr_probe <photo>`: decode + quality + OCR timings and the first tokens for one photo.

## Status (Phase 1)
All endpoints exist with contract types. `/api/scan` validates and decodes uploads, then returns the fixture. `/api/recheck` and `/api/catalog` use the engine adapter. `/api/ask`, `/api/profile/parse` and `/api/explain` return fixtures. `/api/health` is real. Image decoding, quality checks and word-level OCR are implemented and tested.
