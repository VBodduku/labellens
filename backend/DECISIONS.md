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

## Phase 2
- One structuring call per scan covers all panels: the LLM schema has a `panels[]` list (one level, no recursion); alignment and merge then run per panel.
- LLM-facing JSON schema: `$ref`s inlined and **every property required** (null / [] allowed). With optional fields, constrained decoding let gemma3 skip `ingredients` entirely.
- Window search (alignment step 2) only accepts windows between 0.8x and 1.5x(+4) of the item's length, so "Sugar" cannot verify "Invert Sugar Syrup", and over-wide citations get narrowed. Ties go to the window nearest the cited tokens.
- Nutrient numbers: verified -> parsed from OCR text (OCR wins, `llm_ocr_number_mismatch:<key>`); located only by the model's box -> kept but `partial`; not found on the photo at all -> amount None, `unreadable`, issue `value_not_on_photo:<key>` (gemma3 invented "175 mg" for a smudged sodium value).
- Sub-ingredient `parent_index` is accepted only if the child's text appears inside the parent's printed text (gemma3 set parent 0 on every item).
- Statement ids `alg_N`, claim ids `clm_N` (same as the fixture).
- Cache key = image bytes + order + panel hints + PROMPT_VERSION + GEMINI_MODEL; language is not part of it (extraction does not depend on it). `ocr_only` results are never cached.
- OCR-only: a token ending in `)`/`),`/`).` resets bracket depth (OCR garbles brackets); nutrition rows are read only below a "Nutrition" heading; veg mark is always `unclear`.
- Scan budget 45 s: the LLM call gets what is left minus 5 s; on timeout or all-providers-failed the scan degrades to OCR-only instead of failing. A route-level 45 s guard returns 503 `LLM_UNAVAILABLE`.
- Router: a provider that times out is skipped for 300 s (like a 429 cooldown). On this M2 Mac, gemma3:4b needs ~120 s for a full extraction (30 tok/s output), so without Gemini the first scan waits 30 s and later scans go OCR-only in ~1 s.
- Ollama `num_ctx` = 8192: the default context truncates the prompt, and the OCR list comes last.
- Gemini: SDK retries disabled (`HttpRetryOptions(attempts=1)`), timeout in ms from `LLM_TIMEOUT_S`; the router owns fallback.
- The FakeLLM fixture `tests/data/ollama_test_label.json` is a real gemma3:4b recording (it includes realistic mistakes). The Gemini recording (`scripts/record_fake_llm.py gemini`) is added once a key is in `.env`.
