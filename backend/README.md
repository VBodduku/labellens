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
- `python -m backend.scripts.smoke_scan <photos_dir> [--url ...]`: scans every packet folder against a running backend and prints a table.
- `python -m backend.scripts.record_fake_llm gemini|ollama`: records a real structuring response for the offline tests.

## Status (Phase 3)
Real pipeline with the real engine: OCR -> LLM structuring (Gemini -> Ollama -> OCR-only) -> evidence alignment -> panel merge -> self-verification -> engine -> term interpretation -> grounded summaries. `/api/ask` (tool-calling agent with guard and keyword fallback), `/api/profile/parse`, `/api/explain` and `/api/recheck` are real. See `DECISIONS.md` and `NOTES_FOR_OTHERS.md`.
