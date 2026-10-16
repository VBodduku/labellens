# LabelLens backend (Part 2)

FastAPI service that turns label photos into an evidence-linked `ScanResult`
(see `docs/PART2_BACKEND_SPEC.md`). Pipeline: quality -> OCR (word boxes) -> LLM structuring
(Gemini -> backup key -> Ollama -> OCR-only) -> evidence alignment -> panel merge ->
self-verification -> rules engine -> term interpretation -> grounded summaries.

## Run locally (from the repo root)
```bash
python3.12 -m venv .venv            # Python 3.12: rapidocr-onnxruntime does not support 3.13
.venv/bin/pip install -r backend/requirements.txt -r engine/requirements.txt
cp .env.example .env                # GEMINI_API_KEY (Google AI Studio), ENGINE_MODE=real
                                    # optional: GEMINI_FALLBACK_MODEL (default gemini-flash-lite-latest)
.venv/bin/uvicorn backend.app.main:app --reload --port 8000
.venv/bin/python -m pytest engine/tests backend/tests            # add -m live for real Gemini calls
```
(Windows: `.venv\Scripts\python` instead of `.venv/bin/python`.)

## Live demo on the Mac (phone on the same Wi-Fi or the Mac's hotspot)
```bash
ollama serve &                                   # or: brew services start ollama
ollama pull gemma3:4b                            # fallback model (OLLAMA_MODEL in .env)
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000      # terminal 1
.venv/bin/python -m backend.scripts.warm_cache <demo_photos_dir>      # once, before judging
cd frontend && npm run dev                                             # terminal 2 (Vite proxies /api)
cloudflared tunnel --url http://localhost:5173                         # terminal 3: HTTPS link for the phone camera
```
- `warm_cache.py` scans every demo packet in en/te/hi, then rescans: every row should say
  `cache hit yes` and `ok yes` (< 1.5 s). Cached scans need no LLM call at all.
- `curl localhost:8000/api/health` must show `"engine_mode":"real"` and at least one provider `true`.
- Without Gemini, scans answer in OCR-only mode (every section marked incomplete, no summaries).

## Docker
Build from the repo root (the image copies `shared/`, `engine/` and `backend/`):
```bash
docker build -f backend/Dockerfile -t labellens-api .
docker run -p 7860:7860 -e GEMINI_API_KEY=AIza... -e CORS_ORIGINS=http://localhost:5173 labellens-api
curl localhost:7860/api/health
```
The port comes from `$PORT` (default 7860); `OCR_WORKERS` (default 3) limits parallel OCR on small hosts. `backend/Dockerfile.dockerignore` keeps the build
context small (BuildKit). On a Mac without Docker Desktop: `brew install colima docker docker-buildx`,
`colima start --cpu 2 --memory 4 --disk 20`.

## Deploy to Render (free web service)
Hugging Face Docker Spaces now need a paid PRO plan, so the public backend runs on Render's free tier
(512 MB RAM; the service sleeps after 15 min idle and takes about a minute to wake up).
1. Sign up at https://render.com with GitHub and allow access to the `labellens` repository.
2. Dashboard -> **New** -> **Web Service** -> pick the repository.
   - **Branch**: `main` (or `part-2-backend` before the merge)
   - **Language / Runtime**: Docker
   - **Dockerfile Path**: `backend/Dockerfile`  - **Docker Build Context Directory**: `.` (repo root)
   - **Instance Type**: Free
   - **Health Check Path** (Advanced): `/api/catalog`
3. **Environment Variables** (same page, or later under *Environment*):
   - `GEMINI_API_KEY` = your AI Studio key (and `GEMINI_API_KEY_BACKUP` if you have one)
   - `ENGINE_MODE` = `real`
   - `CORS_ORIGINS` = `https://<frontend>.vercel.app` (comma-separate several; add `http://localhost:5173` for local dev)
   - `OCR_WORKERS` = `1` (keeps memory inside 512 MB; panels are read one after another)
   - Render sets `PORT` itself; the image listens on it.
4. **Create Web Service**. The first build takes ~5-10 min. Then check
   `curl https://<service>.onrender.com/api/health` -> `"engine_mode":"real"`, `"gemini":true`.
   Ollama is not available on Render, so `"ollama":false` is expected.
5. Frontend: set `VITE_API_BASE_URL=https://<service>.onrender.com` in Vercel and redeploy it.
   Open the backend URL once before a demo to wake it up.
6. If Render reports "out of memory" (Events tab): check `OCR_WORKERS=1`; a scan of 3 photos then
   reads them one by one (slower, same result).

## Scripts
- `make_test_label [out.png]` - draws the fixture's OCR tokens onto a PNG (default `.cache/test_label.png`).
- `ocr_probe <photo>` - decode + quality + OCR timings and the first tokens for one photo.
- `smoke_scan <photos_dir> [--url]` - scans every packet folder and prints a table with latency stats.
- `warm_cache <photos_dir> [--url] [--lang ...]` - fills the demo cache and proves cache hits are fast.
- `record_fake_llm gemini|ollama` - records a real structuring response for the offline tests.

Run each as `python -m backend.scripts.<name>` from the repo root.
