# Part 2 — Backend + AI pipeline · phase prompts (System B, Claude Code, worktree `labellens-part2`, branch `part-2-backend`)

Paste one phase at a time. Wait for the PHASE REPORT, verify it yourself (2 minutes), then paste the next one.

---

## Phase 1 · Skeleton, fixtures API, images, quality, OCR (0–25 %)

```
You are building Part 2 (backend + AI pipeline) of LabelLens. First read CLAUDE.md, then docs/00_MASTER_SPEC.md completely, then docs/PART2_BACKEND_SPEC.md completely, then shared/contract.py, shared/engine_interface.py, shared/engine_stub.py, shared/messages.en.json and shared/fixtures/. Confirm you are on branch part-2-backend. You may only write inside backend/. Run everything from the repo root.

Goal: a running FastAPI service with the full API surface (serving fixtures where real logic doesn't exist yet), plus real image handling, quality checks and word-level OCR.

Do:
1. backend/requirements.txt (pinned major versions), package layout from spec §3, config.py from .env (see .env.example), logging_setup.py, engine_adapter.py (ENGINE_MODE stub|real; real = `import engine` lazily so it works before Part 3 exists).
2. main.py: app factory, CORS, exception handlers mapping to ErrorResponse, request-id middleware with per-stage timings.
3. All endpoints from master spec §6 exist with the contract types. For now: /api/scan returns shared/fixtures/scan_result.json after validating the upload (file count/size/type → proper errors); /api/recheck runs engine_adapter.evaluate on the posted extraction; /api/ask, /api/profile/parse, /api/explain return their fixtures; /api/catalog uses engine_adapter; /api/health real.
4. pipeline/images.py and pipeline/quality.py per spec §4.1 (EXIF transpose, resize, blur/glare/brightness/resolution). pipeline/ocr.py per spec §4.2: RapidOCR loaded once at startup, run in a thread pool, line → word token splitting, normalised boxes, reading order, token ids img_N:tK.
5. scripts/make_test_label.py: draws the tokens from shared/fixtures/scan_result.json onto a white PNG at their boxes with Pillow, so OCR has a known test image. Unit tests: token splitting, reading order, quality metrics on synthetic blurred/dark images, OCR on the test PNG finds ≥ 90 % of fixture words with boxes overlapping the fixture boxes (IoU ≥ 0.3).
6. API tests with FastAPI TestClient for every endpoint (validation errors, size limits, fixture responses).
7. DECISIONS.md and NOTES_FOR_OTHERS.md in backend/.

Done when: `python -m pytest backend/tests` passes; `uvicorn backend.app.main:app --reload` serves all endpoints; committed in small steps and pushed (git push origin HEAD). Finish with the PHASE 1 REPORT from CLAUDE.md, including OCR timing for one real phone photo of a food label.
```

---

## Phase 2 · LLM structuring, evidence alignment, merge, cache, fallbacks (25–55 %)

```
Phase 2 for Part 2. Re-read docs/PART2_BACKEND_SPEC.md §4.3–4.5, §4.8, §4.9 and §5. Check the current google-genai SDK documentation for structured JSON output with a Pydantic schema, image input, timeouts and error types before writing the client.

Goal: a real /api/scan that turns 1–3 photos into an evidence-linked ScanResult using Gemini, falling back to Ollama and then OCR-only, with the stub engine.

Do:
1. llm/base.py, llm/gemini.py (GEMINI_MODEL, temperature 0, schema-constrained JSON, 429 handling with cooldown + GEMINI_API_KEY_BACKUP), llm/ollama.py (/api/chat with base64 images and `format` JSON schema), llm/router.py (order, timeouts, one schema-repair attempt, provider status for /api/health).
2. pipeline/llm_schema.py (flat, token-citing LLMExtraction from spec §4.3) and prompts/structure.md with every rule in §4.3; PROMPT_VERSION constant.
3. pipeline/structure.py: images + compact token list → LLMExtraction (cap tokens as specified).
4. pipeline/align.py (spec §4.4) — verified / approximate / unverified evidence, one Evidence per printed line, numbers parsed from OCR text with mismatch issues, contract ids. This is the heart of the product: write thorough unit tests.
5. pipeline/merge.py (spec §4.5) with tests for every rule.
6. cache.py (spec §4.8) and pipeline/ocr_only.py (spec §4.9, all sections complete=false).
7. pipeline/orchestrator.py: steps 3–9 + 11 of master spec §5.1 using engine_adapter (stub for now; skip interpretation/summaries/verification until Phase 3 but leave clean hooks). Real /api/scan now uses it. Parallelise OCR across panels.
8. scripts/smoke_scan.py: posts every photo folder in a directory, prints a table (provider, duration, #ingredients, % verified evidence, sections complete?, veg mark, cache hit).
9. Tests with a FakeLLM recorded from one real Gemini response, plus an opt-in `-m live` test.

Verify with real photos of at least 5 packets the humans took (ask them for the folder). Targets: p50 ≤ 8 s with Gemini, ≥ 80 % ingredients verified. Then unset GEMINI_API_KEY → Ollama path works; stop Ollama → OCR-only path works; nothing crashes.
Done when: tests pass, smoke table pasted in the report, committed and pushed. PHASE 2 REPORT, including the smoke table and anything the engine or frontend team must know.
```

---

## ⏸ Merge 1 (≈55 %) — humans
Follow docs/SETUP_AND_GIT.md "Merge 1" (engine first, then backend, then frontend). Then in `labellens-part2`:
`git fetch origin && git merge origin/main`, and set `ENGINE_MODE=real` in this worktree's `.env`.

---

## Phase 3 · Self-verification, interpretation, summaries, agent, profile parsing (55–80 %)

```
Phase 3 for Part 2. main (with the real engine) has been merged into this branch; set ENGINE_MODE=real, pip install -r engine/requirements.txt, and run `python -m pytest engine/tests backend/tests` first. Re-read spec §4.6, §4.7, §6.

Goal: the "advanced" layer — a pipeline that checks itself, an agent that answers questions safely, and natural-language profile setup.

Do:
1. pipeline/verify.py (spec §4.6): triggers in order, region crop + upscale + CLAHE + re-OCR + focused LLM re-read (prompts/reread_region.md), acceptance rule, max 2 rounds, 25 s budget, rate-limit skip, RetryRecord for every attempt, UnknownItems with regions for anything unresolved. Test with FakeLLM and with a deliberately blurred real nutrition photo.
2. pipeline/interpret.py (unresolved terms → TermInterpretation, categories filtered to engine.category_vocabulary(), re-evaluate) and pipeline/summarize.py (one call, per-profile ≤25 words in lang, banned-word filter incl. hi/te equivalents, drop on violation). Wire both into the orchestrator.
3. /api/recheck per spec §6 (engine only; summaries regenerated only when lang changed, 8 s budget).
4. agent/: tools.py, agent.py (Gemini function calling, max 4 rounds, ToolCallTrace), prompts/agent_system.md, guard.py (stance vs engine overall, one retry, then template; medical → refusal), templates.py (4 states × en/hi/te — mark hi/te for human review), fallback.py (keyword intent router for Ollama-only/no-LLM). Tests for guard and fallback.
5. /api/profile/parse with prompts/parse_profile.md: en/hi/te and code-mixed input, relation names, severity from wording, catalog validation, unparsed phrases, needs_confirmation always true. Tests with 10 example sentences (FakeLLM).
6. /api/explain: engine first, then LLM (prompts/explain.md) with source "llm", translation for hi/te, in-memory cache.
7. Run smoke_scan.py on all real packets with the real engine and paste the table; check that all four verdict states occur across packets with a standard family (peanut allergy, diabetic, Jain).

Done when: tests pass, the demo story from master spec §2 works against real packets end to end (including a Telugu question), committed and pushed. PHASE 3 REPORT.
```

---

## Phase 4 · Hardening, deployment, demo readiness (80–100 %)

```
Phase 4 for Part 2 — feature freeze. No new features; make it robust and deployable.

Do:
1. Hardening: timeouts on every external call, structured error responses everywhere, request size limits, graceful behaviour when Gemini returns invalid JSON twice, when OCR finds nothing, when images are huge/tiny/rotated/HEIC. Add tests for each.
2. Performance: profile one scan stage by stage; make sure OCR model loads once, panels run in parallel, images are resized before the LLM; p50 ≤ 8 s on the Mac with Gemini.
3. scripts/warm_cache.py for the demo packets; confirm a cache hit returns in < 1.5 s.
4. Deployment: backend/Dockerfile (repo-root context: copies shared/, engine/, backend/; port from $PORT default 7860), and backend/README.md with exact steps to publish to a Hugging Face Docker Space (secrets, ENGINE_MODE=real, CORS_ORIGINS with the Vercel URL) and to run locally for the demo (host 0.0.0.0, Ollama, cloudflared). Build the image locally to prove it works.
5. /api/health shows truthful provider status; logs contain no keys, images or full prompts.
6. Final smoke on every real packet; paste the table and the average/max latency.

Done when: tests pass, Docker image builds and runs, deployed Space answers /api/health, committed and pushed. PHASE 4 REPORT with the deployed URL.
```

---

## Stretch (only if humans say so after Merge 2)

```
Stretch for Part 2: front-of-pack claim check. Add POST /api/claims/check that takes a ScanResult and returns, for each extraction.claim, the back-label evidence that supports or contradicts it (e.g. "No added sugar" vs sugar-alias ingredients; "High protein" vs protein per 100 g and per 100 kcal), with a status of supported / contradicted / cannot_verify. Rules must be deterministic and conservative (cannot_verify whenever the definition is uncertain); the LLM may only map claim text to a claim type. Write the request/response models in backend/ (do not edit shared/) and document them in backend/NOTES_FOR_OTHERS.md for Part 1. Tests required. PHASE REPORT when done.
```
