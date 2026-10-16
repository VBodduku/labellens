# Part 2 decisions (where the spec was silent or had to bend)

- Python 3.12 venv at the repo root: `rapidocr-onnxruntime` 1.4.x (bundles its models, works offline) requires Python < 3.13.
- `opencv-python` instead of `opencv-python-headless`: rapidocr-onnxruntime depends on `opencv-python`; installing both clobbers the shared `cv2` module.
- OCR words come from RapidOCR per-character boxes (`return_word_box=True`); a gap > 0.45 x line height starts a new word, because the recogniser drops spaces between Latin words ("EdibleVegetable"). The spec's proportional split is the fallback when a line has no character boxes. Fixture-label recall went from 80 % to 96 %.
- `glare_ratio` follows the contract (fraction of pixels with every channel >= 250). A digital pure-white page scores very high; real photos rarely clip paper. Blur (100) and glare (3 %) thresholds are provisional until calibrated on real packet photos.
- `cropped_edge`: at least 3 tokens and at least 10 % of an image's tokens within 1 % of a border.
- Error codes: no images -> 400 `VALIDATION`; > MAX_IMAGES -> 400 `TOO_MANY_IMAGES`; file > MAX_IMAGE_MB or body > MAX_IMAGES x MAX_IMAGE_MB + 1 MB -> 413 `BAD_IMAGE`; undecodable/unsupported file -> 422 `BAD_IMAGE`; unknown route -> 404 `NOT_FOUND`; anything unexpected -> 500 `INTERNAL` without details.
- Accepted image formats: JPEG (incl. MPO), PNG, WebP; HEIF only if the installed Pillow can open it (no extra plugin).
- Phase 1 `/api/scan` validates the form, decodes every image, then returns `shared/fixtures/scan_result.json` with the requested `lang`.
- `/api/health`: Gemini is "up" when a key is set and `GET v1beta/models` returns 200 (no generation quota used); Ollama when `GET /api/tags` returns 200. 3 s timeout each, cached 60 s.
- Extra modules beyond the spec tree: `errors.py` (ApiError), `fixtures.py` (validated fixture loading), `provider_probe.py` (health checks), `pipeline/assemble.py` (EngineOutput -> ScanResult, shared by scan and recheck), `scripts/ocr_probe.py` (time OCR on one photo).
- `backend/pytest.ini` holds pytest config (root config files belong to `main`).
