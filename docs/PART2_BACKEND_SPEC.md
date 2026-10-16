# Part 2 — Backend + AI pipeline (FastAPI)

**Machine:** System B (Mac) · **Tool:** Claude Code · **Branch:** `part-2-backend` (worktree folder `../labellens-part2`) · **Folder you own:** `backend/` only
**Read first:** `docs/00_MASTER_SPEC.md` (whole, especially §5, §6, §9), `shared/contract.py`, `shared/engine_interface.py`, `shared/engine_stub.py`, `shared/fixtures/*`.

You turn photos into a trustworthy, evidence-linked `ScanResult`. Until Merge 1 you call the engine through `shared/engine_stub.py` (`ENGINE_MODE=stub`); after the merge you switch to the real `engine` package without code changes.

---

## 1. Goals

1. **Grounded extraction:** every ingredient, allergen statement and nutrient value is tied to OCR word boxes on the photo, or explicitly marked approximate / unverified.
2. **Honest completeness:** section `complete` flags and unreadable regions are reliable — the engine's "Not listed" depends on them.
3. **Self-verification:** detect likely misreads and truncation, re-read only the problem region, log it.
4. **Resilience:** Gemini → backup key → Ollama → OCR-only, with no crash and an honest result each time.
5. **Agent + helpers:** `/api/ask` (tool-calling), `/api/profile/parse`, `/api/explain`, summaries in en/hi/te.

---

## 2. Stack

Python 3.11/3.12 · FastAPI · Uvicorn · Pydantic v2 · `google-genai` · Ollama (HTTP API at `OLLAMA_BASE_URL`) · `rapidocr-onnxruntime` · `opencv-python-headless` · Pillow · `rapidfuzz` · `python-dotenv` · `httpx` · pytest.
Check the current `google-genai` docs for exact call signatures (structured JSON output with a schema, image parts, function calling) before writing the client — the SDK changes often.

---

## 3. Folder structure

```
backend/
├── __init__.py
├── requirements.txt
├── Dockerfile               build context = repo root (copies shared/, engine/, backend/)
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py              app factory, CORS, routers, exception handlers -> ErrorResponse
│   ├── config.py            settings from env (see .env.example)
│   ├── logging_setup.py     one JSON line per request: id, route, stage timings, provider, retries
│   ├── engine_adapter.py    ENGINE_MODE stub|real -> same 5 functions
│   ├── cache.py             disk cache keyed by sha256(image bytes...) + lang + prompt version + model
│   ├── api/
│   │   ├── routes_scan.py   POST /api/scan, POST /api/recheck
│   │   ├── routes_ask.py    POST /api/ask
│   │   └── routes_misc.py   GET /api/health, GET /api/catalog, POST /api/profile/parse, POST /api/explain
│   ├── pipeline/
│   │   ├── orchestrator.py  the scan flow (master spec §5.1 steps 3–11)
│   │   ├── images.py        decode, EXIF transpose, resize, ids img_0..
│   │   ├── quality.py       blur / glare / brightness / resolution / edge-crop heuristics
│   │   ├── ocr.py           RapidOCR wrapper -> OcrToken (word-level, normalised boxes, reading order)
│   │   ├── llm_schema.py    LLM-facing extraction schema (flat, token-citing)
│   │   ├── structure.py     builds the prompt + calls LLM -> LLMExtraction
│   │   ├── align.py         LLMExtraction + tokens -> contract LabelExtraction with Evidence
│   │   ├── merge.py         multi-panel merge
│   │   ├── verify.py        self-verification loop
│   │   ├── interpret.py     unresolved terms -> TermInterpretation
│   │   ├── summarize.py     per-profile grounded summaries in lang
│   │   └── ocr_only.py      degraded mode when every LLM is down
│   ├── llm/
│   │   ├── base.py          LLMClient protocol: generate_json(...), chat_with_tools(...)
│   │   ├── gemini.py
│   │   ├── ollama.py
│   │   ├── router.py        fallback chain, timeouts, 429 cooldown, backup key
│   │   └── prompts/         structure.md, reread_region.md, interpret.md, summarize.md, agent_system.md, parse_profile.md, explain.md
│   └── agent/
│       ├── tools.py         get_profiles, get_verdict, find_evidence, explain_ingredient, get_nutrition
│       ├── agent.py         tool loop (max 4 rounds), trace recording
│       ├── guard.py         stance check vs engine verdicts, medical refusal
│       ├── templates.py     fixed answer templates for 4 states × en/hi/te (humans review hi/te)
│       └── fallback.py      deterministic intent router used when only Ollama/no LLM is available
├── scripts/
│   ├── make_test_label.py   draws shared/fixtures tokens onto a PNG with Pillow (OCR test image)
│   ├── smoke_scan.py        POST a folder of photos, print a summary table
│   └── warm_cache.py        scan the demo packets before judging
└── tests/                   pytest, all offline (FakeLLM + stub engine)
```

Run from the **repo root**: `uvicorn backend.app.main:app --reload --port 8000`, `python -m pytest backend/tests`.

---

## 4. The scan pipeline in detail

### 4.1 Images (`images.py`, `quality.py`)
- Accept 1–`MAX_IMAGES` files, each ≤ `MAX_IMAGE_MB`. JPEG/PNG/WebP/HEIC-if-Pillow-supports; otherwise `BAD_IMAGE` with a helpful message.
- `ImageOps.exif_transpose`, convert RGB, resize to ≤ 2000 px long side for OCR and ≤ 1600 px for the LLM.
- Quality: Laplacian variance on a 1024 px grayscale copy (`blurry` below a calibrated threshold), glare ratio (`glare` above ~3 %), mean brightness (`too_dark` < 60), short side < 600 px (`low_resolution`), dense OCR tokens touching an image border (`cropped_edge`, computed after OCR). `ok = not issues`. Only reject when nothing at all is readable.

### 4.2 OCR (`ocr.py`)
- RapidOCR returns line-level boxes (4 points) + text + score. Split each line into **word tokens**, distributing the line's width proportionally to character counts (good enough for highlighting), and convert to normalised axis-aligned `Box`es. Token ids `img_0:t0…`.
- Sort tokens in reading order (top-to-bottom by line centre, then left-to-right; tolerate slight rotation).
- Load the OCR engine once at startup (it's slow to initialise). Run OCR in a thread pool so the event loop isn't blocked.
- RapidOCR's default models read Latin text well; Hindi/Telugu text may not be recognised — that's expected; the LLM still reads it and evidence falls back to `approximate`.

### 4.3 Structuring (`llm_schema.py`, `structure.py`, `prompts/structure.md`)
LLM input: the image(s) + a compact token list per image: one line per token `t12|Sugar,` (cap ≈ 1500 tokens; if more, drop tokens with confidence < 0.3 first).

LLM output schema (`LLMExtraction`) — **flat** (Gemini's schema support for recursion is limited): every item cites `token_ids` (strings like `img_0:t12`), and may give `box_2d` `[ymin, xmin, ymax, xmax]` on a 0–1000 scale plus `image_id` when there are no tokens (non-Latin text, symbols).
- `product_name`, `languages`
- `ingredients[]`: `text`, `token_ids`, `percentage`, `parent_index` (for sub-ingredients, null otherwise), `readability`
- `ingredients_section`: `presence`, `complete`, `issues[]`, `unreadable_token_ids[]`, `unreadable_box_2d[]`
- `allergen_statements[]`: `type`, `text`, `items[]`, `token_ids`
- `allergen_section`, `nutrition_section`: as above
- `nutrition`: `serving_size`, `serving_unit`, `servings_per_pack`, `pack_size`, `pack_unit`, `rows[]` with `key` (one of `NUTRIENT_KEYS`), `label`, `values[]` (`basis`, `amount` or null, `unit`, `text`, `token_ids`, `readability`)
- `veg_mark`: `value`, `image_id`, `box_2d`
- `claims[]`: `text`, `token_ids`

Prompt rules (put them in `structure.md`, version it with `PROMPT_VERSION`):
- Transcribe, never infer. If text isn't visible, it doesn't exist. Never compute or convert numbers; copy them as printed.
- Mark anything blurred, cut off, folded or covered as `partial`/`unreadable` and list it as unreadable.
- `ingredients_section.complete = true` only when the start ("Ingredients:") and a clear end (final full stop, or the next heading/statement) are both visible and nothing is cut by the image edge.
- Map nutrition labels to keys (Energy/Calories → `energy_kcal`; if only kJ is printed, set unit `kJ`; "Salt" → key `other` with label "Salt" — the engine converts).
- Basis from column headers ("per 100 g", "per serve (30 g)", "per pack").
- Veg mark: a square outline with a filled circle (green = veg) or a filled triangle/circle in brown (non-veg).
- Output JSON only, matching the schema; temperature 0.

### 4.4 Alignment (`align.py`) — the core of "evidence"
For every cited span:
1. Join the cited tokens' text; `rapidfuzz.fuzz.token_set_ratio(item_text, joined) >= 85` → `verified`, box = union of those tokens (split into one Evidence per printed line, like the fixture does).
2. Else slide a window (1–12 consecutive tokens, same image) over all tokens and take the best `partial_ratio`; ≥ 88 → `verified` with that window.
3. Else if `box_2d` given → convert to normalised `Box`, status `approximate`.
4. Else `unverified`, no box.
Then build contract objects: ids `ing_0`, sub-ingredients `ing_3_0`; `NutrientValue.amount` must be **parsed from the printed text** of the verified tokens when possible (guard against the LLM "fixing" numbers); if the LLM amount and the OCR text disagree, prefer the OCR text and add an issue `llm_ocr_number_mismatch`.

### 4.5 Multi-panel merge (`merge.py`)
- Ingredients: take the list from the panel whose section is most complete; add evidence from duplicate items found on other panels (fuzzy name ≥ 90). If two panels each hold a different partial list, keep the most complete and add an issue.
- Nutrition rows by key; prefer readable values; two readable values differing > 2 % → keep the higher-confidence one and add issue `panel_disagreement`.
- Allergen statements: union, deduplicated by type + items.
- Veg mark: `non_veg` on any panel wins; else `veg` if any; else `unclear` / `not_found`.
- Claims: union.

### 4.6 Self-verification loop (`verify.py`)
Triggers (checked in order, max **2** retry rounds, total budget 25 s, skip when rate-limited):
1. `engine.analyze_nutrition()` → `consistency.status == "inconsistent"` (suspect keys).
2. Ingredient section `complete == false` with issue `truncated_at_image_edge` or unreadable spans.
3. A nutrient needed by any profile threshold is unreadable.
4. More than 30 % of evidence is `unverified`.
Action: crop the region (union of the section's tokens or the unreadable boxes, padded 8 %), upscale ×2 (cap 2000 px), enhance contrast (CLAHE on the L channel), re-run OCR on the crop, map crop tokens back into full-image coordinates, and ask the LLM with `reread_region.md` to re-read only that section. Accept the new reading if it is more complete/readable or fixes the consistency check; otherwise keep the original.
Record a `RetryRecord` for every attempt (`reason`, `action`, `outcome`: `resolved` / `unchanged` / `skipped_rate_limit` / `skipped_budget`). Anything still unresolved becomes an `UnknownItem` with `region` (image + box) so the UI can offer "Retake this area". Truncation can't be fixed by re-reading — it goes straight to an `UnknownItem` with message `unknown.ingredients_truncated`.

### 4.7 Engine, interpretation, summaries
- `engine.evaluate(extraction, profiles)` → `EngineOutput`.
- If `unresolved_terms` (cap 10): one LLM call (`interpret.md`) with the allowed categories from `engine.category_vocabulary()`; drop any category not in the vocabulary; then `engine.evaluate(..., interpretations)`.
- Summaries (`summarize.md`): one call for all profiles; input = profile names + each result's state, reason_code, English explanation; output `{profile_id: summary}` in the requested language; ≤ 25 words each; must mention unknowns that matter; must not add facts; banned words in any language: "safe", "healthy", "guaranteed" (and their hi/te equivalents — list them in the prompt). Reject and drop a summary that violates rules (the frontend then uses its template).
- Assemble `ScanResult` (`created_at` ISO with offset, `lang`, `contract_version`).

### 4.8 Caching (`cache.py`)
Cache **the merged LabelExtraction** (not the verdicts — profiles change) on disk under `CACHE_DIR`, keyed by sha256 of all image bytes + panel order + `PROMPT_VERSION` + model. Cache hits set `meta.cache_hit = true`. This protects the free tier and makes the live demo instant for pre-scanned packets (`scripts/warm_cache.py`).

### 4.9 OCR-only degraded mode (`ocr_only.py`)
When every LLM fails: locate "ingredients"/"सामग्री"/"పదార్థాలు"-like headings in the OCR text, take text until the next heading or a full stop, split on top-level commas → ingredients with `readability="partial"`; parse "Contains:" / "May contain" lines; nutrition rows via regex on common labels. **All sections `complete=false`** so the engine can never claim "Not listed". `meta.provider = "ocr_only"`.

---

## 5. LLM layer (`llm/`)

- `LLMClient.generate_json(prompt, images, schema, timeout)` and `LLMClient.chat_with_tools(messages, tools, timeout)`.
- **Gemini:** model from `GEMINI_MODEL` (default alias `gemini-flash-latest`), structured output with the Pydantic schema, temperature 0. On 429: read the retry delay if provided, mark the key cooled-down, try `GEMINI_API_KEY_BACKUP`, then Ollama.
- **Ollama:** `POST {OLLAMA_BASE_URL}/api/chat` with base64 images and `format` = JSON schema (structured outputs), `options.temperature = 0`. Vision model from `OLLAMA_MODEL`. Expect it to be slower and weaker: lower the token list cap and accept more `approximate` evidence.
- Router: try in order, each with timeout `LLM_TIMEOUT_S`; validate the JSON against the schema; one repair attempt (send the validation error back) before falling through. Expose last success/failure per provider for `/api/health`.
- Never log images or full prompts; log sizes, durations and outcomes.

---

## 6. Other endpoints

- **`/api/recheck`**: validate, run `engine.evaluate` (+ cached interpretations if you keep them per scan_id in memory — optional), regenerate summaries only if `lang` differs from the original (best effort, 8 s timeout, else omit). No extraction calls.
- **`/api/ask`** (`agent/`):
  - Tools (JSON schemas): `get_profiles()`, `get_verdict(profile_id)`, `find_evidence(query)` (fuzzy search over OCR tokens + extracted items), `explain_ingredient(term)` (engine KB, else note "not in our database"), `get_nutrition(key, basis)`.
  - System prompt (`agent_system.md`): answer in the requested language; only state facts returned by tools; for "is it okay/safe for X" questions, report the engine's verdict and the reasons, never a new judgement; mention unknowns; no medical, dosage or treatment advice → redirect to a doctor; keep answers ≤ 3 sentences; the final message is JSON `{answer, stance, intent, profile_ids, evidence_refs}`.
  - `guard.py`: if `intent == "suitability"` and `stance` ≠ the engine's `overall` for the referenced profile → retry once with a correction note; if still wrong, answer from `templates.py`. `intent == "medical"` → refusal (`grounded=false`, `refusal="medical_advice"`).
  - Record every tool call into `ToolCallTrace` (`result_summary` short and human-readable).
  - `fallback.py` (Ollama-only or no LLM): regex/keyword intent router for the common questions ("okay for <name>", "does it have <term>", "how much <nutrient>") answering from templates.
- **`/api/profile/parse`**: LLM with the catalog keys listed (from `engine.restriction_catalog()`); handles en/hi/te input and code-mixing ("mera beta peanuts se allergic hai"); unknown names → relation words ("Son", "Mother") or "Me"; severity from wording ("allergic" → strict; "avoid", "prefer not", "trying to cut" → preference); thresholds from catalog defaults; anything unmapped → `unparsed`; validate all keys; always `needs_confirmation: true`.
- **`/api/explain`**: `engine.explain_term(term, lang)` → if None, LLM with `explain.md` (short, factual, origin, "may vary" when unsure) marked `source: "llm"`; translate the KB description via LLM for hi/te when needed (cache).
- **`/api/catalog`**: `engine.restriction_catalog()`.
- **`/api/health`**: `{status, providers: {gemini, ollama}, engine_mode}`; provider status cached 60 s; Ollama check = `GET /api/tags`.

---

## 7. Errors, limits, security
- All errors → `ErrorResponse` with the right status (400 validation, 413 too large, 422 bad image, 429 rate limited with `retry_after_s`, 503 all providers down only if even OCR fails, 500 otherwise).
- CORS from `CORS_ORIGINS`. Request body limit. No secrets in logs. `.env` never committed.

## 8. Testing (all offline)
- `FakeLLM` returning recorded JSON; stub engine.
- Unit: token splitting and reading order, alignment statuses (verified / approximate / unverified), number parsing from OCR text, merge rules, verify-loop triggers and budget, interpretation vocabulary filtering, summary banned-word filter, guard behaviour, parse validation.
- API: `TestClient` for every endpoint; `/api/scan` with the test PNG from `scripts/make_test_label.py` and FakeLLM must produce a valid `ScanResult` whose evidence boxes overlap the expected tokens.
- One opt-in live test (`-m live`) that calls Gemini with a real photo.

## 9. Deployment
- **Live demo:** run on the Mac (`uvicorn ... --host 0.0.0.0`) with Ollama local; the frontend's Vite dev server proxies `/api`.
- **Public link:** Hugging Face Spaces (Docker SDK, free CPU). The Space needs `Dockerfile` at its root listening on port 7860 — `scripts/` or README documents copying `backend/`, `engine/`, `shared/` and the Dockerfile into the Space repo. Set `GEMINI_API_KEY` as a Space secret, `ENGINE_MODE=real`, `CORS_ORIGINS` = the Vercel URL. Ollama is not available there (Gemini + OCR-only fallback only). Render is the backup host if the image fits its free memory.

## 10. Done criteria
- `python -m pytest backend/tests` green on the Mac.
- With `ENGINE_MODE=stub` and a real Gemini key: `scripts/smoke_scan.py` on 5 real packet photos returns valid `ScanResult`s, p50 ≤ 8 s, ≥ 80 % of ingredients `verified`.
- Pulling the Gemini key → Ollama answers; stopping Ollama too → OCR-only answers; nothing crashes.
- The self-verification loop demonstrably fixes or flags a deliberately blurred nutrition photo.
- After Merge 1 (`ENGINE_MODE=real`) the fixture scenario and real packets produce all four states correctly.

## 11. Do not
- Do not write inside `frontend/`, `engine/` or `shared/`. If the contract needs a field, write it in `backend/NOTES_FOR_OTHERS.md` and tell the team.
- Do not let the LLM decide verdicts. Do not put verdict logic in the backend — it belongs to the engine.
- Do not improve `shared/engine_stub.py`.
- Do not use paid services or send images anywhere except the configured LLM providers.
