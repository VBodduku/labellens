# Notes from Part 2 (backend) for the other parts

## For Part 1 (frontend)
- Error bodies are always `ErrorResponse`. Besides the codes in the master spec, `NOT_FOUND` (404) can appear for a wrong URL; treat it like `INTERNAL`.
- An oversized photo returns **413 with `error_code: "BAD_IMAGE"`** and a message like "Each photo must be smaller than 8 MB."
- A photo with no readable text at all returns **422 `BAD_IMAGE`** ("We could not read any text…").
- `/api/scan` almost never fails because of the LLM: when Gemini and Ollama are both unavailable the result comes back with `extraction.meta.provider == "ocr_only"`. In that mode every section has `complete: false`, ingredients are `readability: "partial"`, the veg mark is `unclear`, and `product_name` is null. Showing a "basic reading — AI unavailable" banner would be honest.
- A 503 `LLM_UNAVAILABLE` only happens if a scan exceeds 45 s.
- Every response carries an `X-Request-ID` header (exposed through CORS); showing it in error toasts helps us find the log line.
- `ProfileReport.summary` is filled only when Gemini is available and the summary passed every check; otherwise it is null -> use your template summary.
- New `UnknownItem`s from the backend: `message_key: "unknown.retake_region"` (section `nutrition` or `ingredients`, `detail` = the reason, e.g. `nutrition_value_unreadable:sodium_mg`) and `unknown.ingredients_truncated`, both always with a `region` for "Retake this area".
- `extraction.meta.retries` lists every self-check attempt (`resolved`, `unchanged`, `skipped_budget`, `skipped_rate_limit`, `unresolved` with action `ask_user_retake`) for the "double-checked" badge.
- `/api/ask` without Gemini answers from a keyword router (still grounded, with tool_calls). Medical questions return `refusal: "medical_advice"`, `grounded: false`.
- `/api/profile/parse` may return `warnings` such as "Also mentioned: Jain. Add it to the right person if it applies." and `basic_parsing` (no LLM) — show them on the confirmation screen.
- `/api/explain` returns 503 `LLM_UNAVAILABLE` for a term that is not in the KB when Gemini is unavailable.

- Deployed backend: set `VITE_API_BASE_URL` to the Space URL (`https://<hf-user>-labellens-api.hf.space`). Tell us the Vercel URL so it goes into the Space's `CORS_ORIGINS`.
- HEIC photos are accepted now; files over 50 MP get 422 `BAD_IMAGE`; bodies over the limit get 413 (also for chunked uploads).

## For Part 3 (engine)
- `ENGINE_MODE=real` imports the top-level `engine` package and requires all five functions from `shared/engine_interface.py` to be importable from `engine/__init__.py`.
- `SectionStatus.issues` strings the backend emits: `unreadable_span`, `truncated_at_image_edge` (from the LLM), `llm_ocr_number_mismatch` / `llm_ocr_number_mismatch:<nutrient_key>`, `value_not_on_photo:<nutrient_key>`, `panel_disagreement:<nutrient_key>`, `panels_partial_lists`, `ocr_only`.
- A nutrient value with `amount: null` is always `readability: "unreadable"`; a value located only by the model's box has `readability: "partial"` (not cross-checked against OCR).
- Salt is passed as `key: "other"` with `raw_label` "Salt" (as the spec says, the engine converts).

- In `ocr_only` mode every ingredient is `partial`, and the engine emits one `unknown.unreadable_span` per ingredient and per nutrient value (30+ items on the fixture label). Grouping them per section would make the "What we couldn't read" panel usable.
- KB gap seen in testing: carrageenan (INS 407) is not in the KB.

## For main / humans
- Backend needs Python 3.12 (not 3.13) because of `rapidocr-onnxruntime`.
- On the M2 demo Mac, gemma3:4b (Ollama) is too slow for full label extraction within the 45 s scan budget (~120 s). Without Gemini the app answers in OCR-only mode. Warm the cache with Gemini before judging (`scripts/warm_cache.py`, Phase 4).
- Docker image builds from the repo root with `docker build -f backend/Dockerfile .`; it copies `engine/*.py` and `engine/kb/` — keep any new runtime engine files in those places (or tell us).
- Native-speaker review needed for the hi/te strings in `backend/app/wording.py` and `backend/app/agent/templates.py` (marked `REVIEW`).
- No contract changes requested.
