# Notes from Part 2 (backend) for the other parts

## For Part 1 (frontend)
- Error bodies are always `ErrorResponse`. Besides the codes in the master spec, `NOT_FOUND` (404) can appear for a wrong URL; treat it like `INTERNAL`.
- An oversized photo returns **413 with `error_code: "BAD_IMAGE"`** and a message like "Each photo must be smaller than 8 MB."
- A photo with no readable text at all returns **422 `BAD_IMAGE`** ("We could not read any text…").
- `/api/scan` almost never fails because of the LLM: when Gemini and Ollama are both unavailable the result comes back with `extraction.meta.provider == "ocr_only"`. In that mode every section has `complete: false`, ingredients are `readability: "partial"`, the veg mark is `unclear`, and `product_name` is null. Showing a "basic reading — AI unavailable" banner would be honest.
- A 503 `LLM_UNAVAILABLE` only happens if a scan exceeds 45 s.
- Every response carries an `X-Request-ID` header (exposed through CORS); showing it in error toasts helps us find the log line.

## For Part 3 (engine)
- `ENGINE_MODE=real` imports the top-level `engine` package and requires all five functions from `shared/engine_interface.py` to be importable from `engine/__init__.py`.
- `SectionStatus.issues` strings the backend emits: `unreadable_span`, `truncated_at_image_edge` (from the LLM), `llm_ocr_number_mismatch` / `llm_ocr_number_mismatch:<nutrient_key>`, `value_not_on_photo:<nutrient_key>`, `panel_disagreement:<nutrient_key>`, `panels_partial_lists`, `ocr_only`.
- A nutrient value with `amount: null` is always `readability: "unreadable"`; a value located only by the model's box has `readability: "partial"` (not cross-checked against OCR).
- Salt is passed as `key: "other"` with `raw_label` "Salt" (as the spec says, the engine converts).

## For main / humans
- Backend needs Python 3.12 (not 3.13) because of `rapidocr-onnxruntime`.
- On the M2 demo Mac, gemma3:4b (Ollama) is too slow for full label extraction within the 45 s scan budget (~120 s). Without Gemini the app answers in OCR-only mode. Warm the cache with Gemini before judging (`scripts/warm_cache.py`, Phase 4).
- No contract changes requested.
