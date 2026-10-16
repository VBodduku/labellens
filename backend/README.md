# LabelLens backend (Part 2)

FastAPI service that turns label photos into an evidence-linked `ScanResult`
(see `docs/PART2_BACKEND_SPEC.md`). Pipeline: quality -> OCR (word boxes) -> LLM structuring
(Gemini -> backup key -> Ollama -> OCR-only) -> evidence alignment -> panel merge ->
self-verification -> rules engine -> term interpretation -> grounded summaries.

## Run locally (from the repo root)
```bash
python3.12 -m venv .venv            # Python 3.12: rapidocr-onnxruntime does not support 3.13
.venv/bin/pip install -r backend/requirements.txt -r engine/requirements.txt
cp .env.example .env                # GEMINI_API_KEY=AIza... (Google AI Studio), ENGINE_MODE=real
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
The port comes from `$PORT` (default 7860). `backend/Dockerfile.dockerignore` keeps the build
context small (BuildKit). On a Mac without Docker Desktop: `brew install colima docker docker-buildx`,
`colima start --cpu 2 --memory 4 --disk 20`.

## Deploy to a Hugging Face Docker Space (free CPU)
1. One time: `.venv/bin/pip install huggingface_hub` and `.venv/bin/hf auth login` with a **write** token
   from https://huggingface.co/settings/tokens.
2. Publish (creates or updates the Space, sets `ENGINE_MODE=real`, `CORS_ORIGINS`, `CACHE_DIR`, uploads,
   then waits for `/api/health`):
   ```bash
   .venv/bin/python -m backend.scripts.publish_space <hf-user>/labellens-api --cors https://<frontend>.vercel.app
   ```
3. Add the secret yourself: Space -> Settings -> Variables and secrets -> New secret
   `GEMINI_API_KEY` (and `GEMINI_API_KEY_BACKUP`). The Space restarts by itself.
4. Check: `curl https://<hf-user>-labellens-api.hf.space/api/health` -> `"gemini":true`.
   Ollama is not available on Spaces, so `"ollama":false` is expected there.
5. Frontend: set `VITE_API_BASE_URL=https://<hf-user>-labellens-api.hf.space` in Vercel. If the Vercel URL
   changes, rerun step 2 with the new `--cors` (or edit the `CORS_ORIGINS` variable in the Space settings).

## Scripts
- `make_test_label [out.png]` - draws the fixture's OCR tokens onto a PNG (default `.cache/test_label.png`).
- `ocr_probe <photo>` - decode + quality + OCR timings and the first tokens for one photo.
- `smoke_scan <photos_dir> [--url]` - scans every packet folder and prints a table with latency stats.
- `warm_cache <photos_dir> [--url] [--lang ...]` - fills the demo cache and proves cache hits are fast.
- `record_fake_llm gemini|ollama` - records a real structuring response for the offline tests.
- `publish_space <user>/<space> [--cors ...]` - deploys to Hugging Face (see above).

Run each as `python -m backend.scripts.<name>` from the repo root.
