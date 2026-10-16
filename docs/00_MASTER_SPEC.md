# LabelLens — Master Spec

> Read this first, whichever part you are building. Then read your own part spec.
> Part 1 (frontend): `docs/PART1_FRONTEND_SPEC.md` · Part 2 (backend + AI pipeline): `docs/PART2_BACKEND_SPEC.md` · Part 3 (rules engine + knowledge base + evaluation): `docs/PART3_ENGINE_SPEC.md`
> The shared contract in `shared/` is the law. If this document and `shared/contract.py` disagree, the contract wins.

---

## 1. The problem, in our words

People make food decisions in seconds, standing in a shop aisle or at home, from a label printed in 6-point text on a curved, glossy packet. The label is technically complete, but practically unreadable:

1. **Hidden names.** Milk appears as *whey*, *casein* or *milk solids*. Sugar appears as *invert syrup*, *maltodextrin*, *dextrose*. Animal products hide behind codes like *INS 120* or *INS 441*. A peanut-allergic child's parent must know all of these.
2. **"Not on the label" is not the same as "not in the food".** A blurry photo, a list cut off at the fold, or a smudged value means we simply *don't know*. Every existing scanner app silently treats "didn't see it" as "it's not there". That is the dangerous failure.
3. **One shopper, many eaters.** In Indian households one person buys for a child with an allergy, a diabetic parent, and a Jain or vegetarian adult. They check the same packet three times in their head.
4. **Language and literacy.** Many caregivers and elders read Telugu or Hindi far more comfortably than English small print.
5. **Trust.** A bare AI answer ("this is safe!") is worthless if you can't see *why*. People need to see the exact words on the packet that caused a flag.

**What we build:** a camera-first web app that reads a food label, structures everything on it, checks it against every family member's profile at once, and for every single flag **points to the exact words on the photo**. It is honest about what it could not read, and explains the result in English, Hindi or Telugu, by text or voice.

**What we are NOT building:** a nutrition coach, a medical tool, a product database, or a "healthier alternatives" recommender. We never tell anyone a product is "safe". We tell them what the label says, what it doesn't say, and what we couldn't read.

---

## 2. Persona and demo story (team: replace with your own if you have a better one)

**Lakshmi, 34, Hyderabad.** Buys groceries for her family:
- **Aarav (8)** — peanut and tree-nut allergy (strict).
- **Thatha (her father, 67)** — diabetic, watches sodium for BP; reads Telugu comfortably, not English small print.
- **Lakshmi herself** — Jain; mild sesame allergy.

**The 90-second demo:** Lakshmi points her phone at a chocolate bar. The camera says "hold steady" and auto-captures when sharp. In ~6 seconds she sees three family cards: **Aarav: Conflict** (peanuts; tap → the word "Peanuts (22%)" lights up on the photo), **Thatha: Conflict** (38 g sugar per 100 g vs his 22.5 g limit) plus **Sodium: can't determine** (the value is smudged; tap "retake this area"), **Lakshmi: Check this** ("natural flavours" doesn't say what it's made from). Thatha asks by voice in Telugu "ఇది నాకు సరిపోతుందా?" (*is this okay for me?*) and hears the answer in Telugu.

The fixture in `shared/fixtures/` is exactly this scenario. Every part can build and demo it before integration.

---

## 3. Product principles (non-negotiable, every part)

1. **Four states, never "safe".** Every restriction check ends in exactly one of:
   - **Conflict** — the label shows something that conflicts.
   - **Check this** (`possible`) — ambiguous ingredient, "may contain", or an AI interpretation.
   - **Not listed** (`not_listed`) — we read the whole relevant section and it isn't there.
   - **Unknown** — split into **Not detected** (part of the section was unreadable; nothing found in the readable part) and **Can't determine** (section missing, value missing, or labels don't carry this information).
2. **Absence requires completeness.** "Not listed" is only allowed when the relevant section was read end to end. Otherwise the answer is Unknown.
3. **Every flag has evidence.** Each Conflict/Check result carries the exact source text and its location on the photo. If we can't locate it, we say so ("unverified").
4. **The AI never decides safety on its own.** Verdicts come from a deterministic, tested rules engine. LLM interpretation of unknown terms can raise a result to "Check this" at most, never to "Conflict".
5. **Degrade, don't die.** Gemini fails → Ollama. Both fail → OCR-only mode with keyword rules. Camera denied → file upload. Speech unsupported → typing. The app always produces an honest answer.
6. **Depth over breadth.** A small number of flows, each one finished: loading states, errors, empty states, mobile, both browsers.

---

## 4. Scope

### 4.1 Locked capabilities (priority order — if time runs short, cut from the bottom)

| # | Capability | Pain it solves | Built by | Acceptance (must all be true) |
|---|---|---|---|---|
| 1 | **Evidence-grounded extraction** with self-verification and correct-and-recheck | Unreadable small print; trust | P2 pipeline, P1 overlay | Each ingredient/nutrient/allergen statement links to its words on the photo; tap a flag → photo zooms to the highlighted words; inconsistent nutrition triggers a focused re-read; user can correct any value and all verdicts update in < 1 s |
| 2 | **Deterministic verdict engine** with India-specific knowledge base, severity, four states, nutrition checks | Hidden names; "not seen" ≠ "absent" | P3 | All rules in §9 implemented and unit-tested; KB covers allergens, Indian diets (veg/egg/vegan/Jain/no onion-garlic), INS/E-numbers, sugar aliases; energy cross-check flags misread values |
| 3 | **Smart capture**: live quality guidance, auto-capture, multi-panel scan | Bad photos cause most unknowns; labels wrap around packs | P1 (client checks), P2 (server check + merge) | Live hints for blur/glare/dark; auto-captures when sharp and steady; up to 3 panels per scan merged into one result with per-panel evidence |
| 4 | **Family profiles**, created by form, typing a sentence, or speaking | One shopper, many eaters | P1 UI, P2 parse endpoint, P3 catalog | One scan → one verdict card per family member; "My son is allergic to peanuts and I'm Jain" → two confirmed profiles |
| 5 | **Ask-the-label voice agent** | "Is this okay for my mother?" | P2 agent, P1 UI | Tool-calling agent answers only from engine results and label evidence; shows the tools it used; refuses medical advice |
| 6 | **Telugu / Hindi / English** results + read-aloud | Language and literacy | P1 i18n + speech, P2 summaries | Verdicts, explanations and profile UI in 3 languages (fixed reviewed strings for verdict states); read aloud short verdict or full explanation |

**Pitch assets (not features):** accuracy test set of 10–15 real packets with hand-labelled truth and measured results (P3), shown on the "How it works" page.

**Platform:** installable PWA (Android + iOS from the same code). On iOS, voice input may be unreliable → typed fallback is always visible.

### 4.2 Stretch (only after everything above is done and demo-tested)
- Two-product comparison with per-100 g normalisation + front-of-pack claim check ("High protein", "No added sugar") against the back label. The extraction already captures `claims`.
- Capacitor wrap for an Android APK / personal iPhone install.

### 4.3 Explicit non-goals
Barcode or product-database lookup · "healthier alternatives" · accounts/login/history server · medical/dosage advice · expiry-date reading · foreign-language (non-Indian) labels · multi-agent systems · custom model training.

---

## 5. Architecture

```
 PHONE / LAPTOP BROWSER (Chrome, Edge)                      MAC (demo host)            CLOUD (free tiers)
 ┌──────────────────────────────────────────┐   HTTPS/JSON   ┌───────────────────────────────────────────┐
 │ PART 1  React PWA                        │ ─────────────▶ │ PART 2  FastAPI  (backend/)                │
 │  • camera + quality worker (blur/glare)  │                │  /api/scan  /api/recheck  /api/ask         │
 │  • multi-panel tray                      │ ◀───────────── │  /api/profile/parse  /api/explain          │
 │  • evidence overlay (SVG over photo)     │   ScanResult   │  /api/catalog  /api/health                 │
 │  • family profiles (IndexedDB)           │                │                                           │
 │  • i18n en/hi/te, speech in/out          │                │  pipeline: quality → RapidOCR (word boxes) │
 │  • mocks from shared/fixtures            │                │   → LLM structuring (cites token ids)      │
 └──────────────────────────────────────────┘                │   → alignment (rapidfuzz) → panel merge    │
                                                             │   → self-verification loop (≤2 retries)    │
                                                             │   → ENGINE → LLM interpretation of unknown │
                                                             │     terms → ENGINE again → summaries (lang)│
                                                             │                                           │
                                                             │  llm/: Gemini Flash ──fail──▶ Ollama (Mac) │
                                                             │  agent/: tool-calling Q&A                  │
                                                             └──────────────┬────────────────────────────┘
                                                                            │ python import (same process)
                                                             ┌──────────────▼────────────────────────────┐
                                                             │ PART 3  engine/  (pure Python, no network) │
                                                             │  KB (JSON) · matcher · verdict rules ·      │
                                                             │  nutrition normalise + consistency ·        │
                                                             │  catalog · explain_term · eval harness      │
                                                             └───────────────────────────────────────────┘
```

### 5.1 One scan, step by step
1. **Capture (P1).** Camera stream → Web Worker computes blur (Laplacian variance), glare (% near-white), brightness, steadiness → hints → auto-capture. User may add up to 3 panels (front/back/side). Images are downscaled client-side to ≤ 2000 px long side, JPEG q≈0.9.
2. **Upload (P1 → P2).** `POST /api/scan` multipart with images, profiles JSON, lang.
3. **Quality (P2).** Server repeats the quality check; attaches `ImageQuality`; rejects only if unusable (`BAD_IMAGE`), otherwise continues and records issues.
4. **OCR (P2).** RapidOCR → word-level `OcrToken`s with boxes and confidences.
5. **Structuring (P2).** LLM gets the image(s) + compact OCR token list (`t12:Sugar,`). Returns JSON (schema-constrained) where every item cites the token ids it came from, marks unreadable parts, section completeness, veg mark, allergen statements, claims, and nutrition rows with basis.
6. **Alignment (P2).** Every cited span is verified against OCR text with rapidfuzz → `verified`; else searched across tokens → `verified`; else model's own box → `approximate`; else `unverified`.
7. **Panel merge (P2).** Duplicate ingredients/rows across panels collapse into one item with evidence from every panel; conflicts between panels are kept and flagged.
8. **Self-verification (P2 using P3).** `engine.analyze_nutrition()` cross-checks energy vs macros. If inconsistent, or a section is truncated/unreadable, or many items are unverified → crop that region, upscale and enhance, re-OCR and re-ask the LLM for just that region. Max 2 retries, 25 s budget. Every attempt is logged in `meta.retries` (the UI shows it as "double-checked").
9. **Engine (P3).** `engine.evaluate()` → annotations, nutrition analysis, per-profile reports, unknowns, unresolved terms.
10. **Interpretation (P2).** Unresolved terms → LLM classifies them strictly into the fixed category vocabulary → `engine.evaluate(..., interpretations)` again (LLM matches cap at "possible").
11. **Summaries (P2).** One-sentence grounded summary per profile in the requested language, generated only from engine results. If the LLM fails, the frontend builds a template summary from message keys.
12. **Display (P1).** Photo with evidence overlay, family verdict cards, results sorted worst-first, nutrition table with per-100 g / per-pack toggle, "What we couldn't read" panel with retake buttons, ask bar, read-aloud.

### 5.2 Recheck (no new LLM calls)
User edits a value or ingredient, changes profiles or language → `POST /api/recheck` with the corrected extraction → engine only → new results in < 500 ms server time.

### 5.3 Ask (agent)
`POST /api/ask` → Gemini function calling with tools `get_profiles`, `get_verdict(profile_id)`, `find_evidence(query)`, `explain_ingredient(term)`, `get_nutrition(key, basis)`. Max 4 tool rounds. The agent can only report engine verdicts; a guard checks the final answer against the referenced verdicts. Medical/dosage questions → polite refusal (`refusal: "medical_advice"`). On Ollama fallback a deterministic intent router answers common questions from templates.

---

## 6. HTTP API (Part 2 implements, Part 1 consumes)

Base URL `VITE_API_BASE_URL` (dev `http://localhost:8000`). All JSON bodies are defined in `shared/contract.py` / `shared/contract.ts`.

| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| GET | `/api/health` | — | `HealthResponse` | Which providers are reachable; engine mode |
| GET | `/api/catalog` | — | `RestrictionCatalogItem[]` | From the engine |
| POST | `/api/scan` | multipart: `images` (1–3), `profiles` (JSON), `lang`, `panel_hints?` | `ScanResult` | p50 ≤ 8 s, hard timeout 45 s |
| POST | `/api/recheck` | `RecheckRequest` | `ScanResult` | Engine only, no LLM extraction; regenerates summaries if lang changed (best effort) |
| POST | `/api/ask` | `AskRequest` | `AskResponse` | Agent |
| POST | `/api/profile/parse` | `ProfileParseRequest` | `ProfileParseResponse` | Always `needs_confirmation: true` |
| POST | `/api/explain` | `ExplainRequest` | `ExplainResponse` | KB first, LLM fallback marked `source: "llm"` |

Errors: HTTP 4xx/5xx with `ErrorResponse` (`BAD_IMAGE`, `TOO_MANY_IMAGES`, `RATE_LIMITED` + `retry_after_s`, `LLM_UNAVAILABLE`, `VALIDATION`, `INTERNAL`). The frontend must show a friendly, specific message for each.

Image ids: the backend names images `img_0..img_2` in upload order; the frontend keeps its own object URLs in the same order to draw overlays.

---

## 7. Repository layout and ownership

```
labellens/
├── CLAUDE.md, AGENTS.md          rules for the AI tools (same content)          [main only]
├── .gitattributes .gitignore .env.example                                     [main only]
├── docs/                         specs (this file + 3 part specs + setup)     [main only]
├── prompts/                      phase prompts for each part                  [main only]
├── shared/                       FROZEN contract, engine interface, stub,     [main only, change protocol]
│                                 messages.en.json, fixtures/
├── frontend/                     Part 1 — React PWA                           [branch part-1-frontend]
├── backend/                      Part 2 — FastAPI + pipeline + agent          [branch part-2-backend]
└── engine/                       Part 3 — rules engine + KB + eval            [branch part-3-engine]
```

**Rule:** a part writes only inside its own folder. Reading anything is fine. Needing a change elsewhere → write it down in your folder's `NOTES_FOR_OTHERS.md` and tell the team; it gets done on `main`.

Python code runs from the repo root (so `import shared`, `import engine`, `import backend` all work): `uvicorn backend.app.main:app --reload`, `python -m pytest engine/tests`.

---

## 8. Shared contract and fixtures

- `shared/contract.py` (Pydantic v2) and `shared/contract.ts` — every data shape.
- `shared/engine_interface.py` — the five engine functions Part 3 implements and Part 2 calls.
- `shared/engine_stub.py` — naive stand-in so Part 2 can run before Part 3 is merged (`ENGINE_MODE=stub`).
- `shared/messages.en.json` — every `message_key` with its English template. Part 1 translates to hi/te.
- `shared/fixtures/` — `sample_label.svg` (a realistic label whose text positions are known), `scan_result.json` (complete result for that label and 3 profiles covering all four states), `profiles.json`, `catalog.json` (**the authoritative list of restriction keys**), `ask_response.json`, `profile_parse.json`, `explain.json`, `health.json`. Regenerate with `python -m shared.fixtures.build_fixtures`.

---

## 9. Verdict semantics (the single source of truth for P3's rules and P1's display)

For each restriction R: `C` = categories from the catalog entry for `R.key`, `S` = R.severity, `T` = R.threshold.
Collect every signal below; the result state is the **worst** one found (conflict > possible > unknown > not_listed). `reason_code`/`message_key` come from the first worst-state signal in table order. `evidence` lists the worst-state signals' evidence first, then supporting evidence from other signals (e.g. Thatha's sugar conflict also shows the "Sugar" and "Invert Sugar Syrup" ingredients). `matches` lists every signal.

| Signal | Condition | State | reason_code | message_key |
|---|---|---|---|---|
| Ingredient (KB) | readable ingredient (or sub-ingredient) whose KB categories ∩ C ≠ ∅ and origin is definite | conflict | `CONFLICT_INGREDIENT` | `verdict.conflict.ingredient` |
| Ingredient (ambiguous) | KB origin `varies` and its *possible* categories ∩ C ≠ ∅, not resolved by a printed qualifier (e.g. "[Soy]", "(plant source)") or by the veg mark | possible | `POSSIBLE_AMBIGUOUS_SOURCE` | `verdict.possible.ambiguous_source` |
| Ingredient (LLM) | term not in KB; LLM interpretation categories ∩ C ≠ ∅ | possible (never conflict) | `POSSIBLE_LLM_INTERPRETATION` | `verdict.possible.llm_interpretation` |
| Sugar alias | R is `diabetes_sugar` and an ingredient is a sugar alias/added sugar | possible (threshold decides conflict) | `POSSIBLE_SUGAR_ALIAS` | `verdict.possible.sugar_alias` |
| Statement "contains" | item maps to a category in C | conflict | `CONFLICT_STATEMENT` | `verdict.conflict.statement` |
| Statement "may contain"/"facility" | item maps to C, S = strict | possible | `POSSIBLE_MAY_CONTAIN` / `POSSIBLE_FACILITY` | `verdict.possible.may_contain` / `.facility` |
| Statement "may contain"/"facility" | item maps to C, S = preference | not_listed (+ note) | `NOT_LISTED_TRACE_NOTE` | `verdict.not_listed.trace_note` |
| Veg mark | `non_veg` and C contains any of meat/poultry/fish_derived/egg_derived/gelatin/animal_derived | conflict | `CONFLICT_VEG_MARK` | `verdict.conflict.veg_mark` |
| Veg mark | `veg` → resolves ambiguity *only* for meat/poultry/fish_derived/egg_derived/gelatin/animal_derived (see note below). Never for dairy/honey/insect_derived/onion/garlic/root_vegetable | — (resolves ambiguity) | — | adds a note to the result |
| Threshold | value for T.nutrient at T.basis is readable and not suspect, value > max | conflict | `CONFLICT_THRESHOLD` | `verdict.conflict.threshold` |
| Threshold | value ≤ max | not_listed | `NOT_LISTED_WITHIN_LIMIT` | `verdict.not_listed.within_limit` |
| Threshold | value unreadable or row missing | unknown / undeterminable | `UNKNOWN_NUTRIENT_MISSING` | `verdict.unknown.nutrient_missing` |
| Threshold | consistency check lists the nutrient as suspect | unknown / undeterminable | `UNKNOWN_SUSPECT_VALUE` | `verdict.unknown.suspect_value` |
| Threshold | no nutrition table at all | unknown / undeterminable | `UNKNOWN_NUTRITION_MISSING` | `verdict.unknown.nutrition_missing` |
| Any | restriction key not in the catalog, or the information is never printed on labels | unknown / undeterminable | `UNKNOWN_NOT_ON_LABELS` | `verdict.unknown.not_on_labels` |
| No signal | ingredient section not found | unknown / undeterminable | `UNKNOWN_SECTION_MISSING` | `verdict.unknown.section_missing` |
| No signal | section complete and no ingredient unreadable | not_listed | `NOT_LISTED_COMPLETE` (or `NOT_LISTED_VEG_MARK` for vegetarian/eggetarian with green mark) | `verdict.not_listed.complete` / `.veg_mark` |
| No signal | section truncated | unknown / not_detected | `UNKNOWN_TRUNCATED` | `verdict.unknown.truncated` |
| No signal | some ingredients unreadable | unknown / not_detected | `UNKNOWN_UNREADABLE` | `verdict.unknown.unreadable` |

Notes:
- **Indian veg mark rule (decided):** treat the green mark as evidence that the product contains no meat, fish, poultry, egg, gelatin or other slaughter-derived ingredients (FSSAI rules require egg-containing foods to carry the brown mark). It says nothing about dairy, honey, insects (e.g. carmine is a known grey area), onion, garlic or root vegetables. A green mark never overrides an explicit conflicting ingredient — if the list says "egg" and the mark is green, the result is **conflict** and the engine adds a note that the label is internally inconsistent.
- A restriction that only has a threshold (e.g. `low_sodium`) is decided by the threshold rows only. `diabetes_sugar` combines threshold + sugar-alias signals.
- `overall` for a profile = worst state across its results.
- Confidence: 1.0 for KB/statement/threshold; 0.7 for ambiguous source; LLM interpretation = model confidence × 0.8; lower by 0.2 when the only evidence is `unverified`.

---

## 10. Tech stack (all free)

| Area | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript (strict), Tailwind CSS, Motion for React (`motion`), React Three Fiber + drei (landing hero only, lazy-loaded), Lenis (smooth scroll on landing/about only), Zustand, react-i18next, idb-keyval, vite-plugin-pwa, lucide-react |
| Backend | Python 3.11/3.12, FastAPI, Uvicorn, Pydantic v2, `google-genai` (Gemini), Ollama via its OpenAI-compatible endpoint or `ollama` client, `rapidocr-onnxruntime`, `opencv-python-headless`, Pillow, `rapidfuzz`, `python-dotenv`, `httpx` |
| Engine | Pure Python 3.11+, Pydantic v2, `rapidfuzz`, pytest |
| LLM | Gemini Flash (`GEMINI_MODEL=gemini-flash-latest`), fallback Ollama on the Mac (vision model, e.g. `gemma3:4b`) |
| Deploy | Vercel (frontend), Hugging Face Spaces Docker or Render (backend). Live demo runs on the Mac (backend + Ollama local; phone on same Wi-Fi/hotspot via Mac's LAN IP) |

---

## 11. Cross-cutting requirements

- **Browsers:** latest Chrome and Edge, desktop and Android. iOS Safari/Chrome: everything except voice input must work.
- **Mobile first:** design at 390 px wide first; no horizontal scroll; tap targets ≥ 44 px; camera flow usable one-handed.
- **Performance:** landing LCP < 2.5 s on mid-range Android; scan/result routes must not load Three.js; 60 fps animations (transform/opacity only); respect `prefers-reduced-motion`.
- **Accessibility:** verdict states never conveyed by colour alone (icon + label + pattern); contrast AA; focus states; screen-reader labels on overlay hotspots.
- **i18n:** en/hi/te for result screens, profiles and voice. Verdict state names and message templates are fixed translations (P1), never LLM-generated. Evidence text stays in the label's original language.
- **Privacy:** images processed in memory; only extraction JSON is cached on the backend (keyed by image hash) to save API quota; profiles live in the browser. Say this on the About page.
- **Free-tier discipline:** one structuring call per scan in the common case; retries only when triggered; cache by image hash; never call the LLM in `/api/recheck` except optional summary regeneration.
- **Errors:** every network call has loading, error and retry UI. No raw stack traces to users. Backend logs one structured line per request.
- **Cross-platform dev:** LF line endings (`.gitattributes`), file names in exact case, no shell-specific npm scripts, Python run from repo root.

---

## 12. Timeline (as % of total hackathon time T; humans fill in clock times once T is known)

| Phase | % of T | Part 1 (Win, Claude) | Part 2 (Mac, Claude) | Part 3 (Mac, Codex) | Humans |
|---|---|---|---|---|---|
| 0 | first 15 min | — | — | — | Push kit to `main`, create branches + worktrees, `.env` keys, Ollama pulled, quick test |
| 1 | 0–25% | Scaffold, design system, mock API, landing + app shell | FastAPI skeleton serving fixtures, quality + OCR pipeline | KB v1, models, matcher, core verdict rules + tests | Buy 10–15 varied packets; photograph each (good + one bad shot) |
| 2 | 25–55% | Capture flow + results with evidence overlay + nutrition | LLM structuring + alignment + merge + fallback + cache, real `/api/scan` | Full rules, nutrition analysis + consistency, catalog, explain, eval harness | Hand-label `truth.json` for each packet (template from P3) |
| **M1** | ~55% | **Merge 1**: P3 → main, P2 → main (`ENGINE_MODE=real`), P1 → main (`VITE_USE_MOCKS=false`). Smoke-test on the Mac with real packets. Everyone pulls main. | | | Lead the smoke test |
| 3 | 55–80% | Profiles + voice + i18n + read-aloud + ask UI + corrections | Self-verification loop, interpretations, summaries, agent, parse, explain | Run eval on real packets, fix top failures, KB expansion (hi/te names), edge cases | Write pitch deck; translations review (native speakers check hi/te strings) |
| **M2** | ~80% | **Merge 2**: everything to main; feature freeze. | | | |
| 4 | 80–100% | PWA, perf, mobile QA, polish, about page with metrics | Deploy, hardening, demo cache warm-up | Final metrics report, docs | Record video, rehearse demo twice, final README |

If behind at M1: drop capability 6 first, then 5 (see §4.1 order).

---

## 13. Integration and merge plan

1. Merge order is always **engine → backend → frontend**, each via a PR into `main` reviewed by a human.
2. Before merging, the part's own checks must pass (P1: `npm run build` + `npm run lint`; P2: `pytest backend/tests`; P3: `pytest engine/tests`).
3. After merge on the Mac: `.env` `ENGINE_MODE=real`, `VITE_USE_MOCKS=false`; run backend + frontend; scan 3 real packets; check all 4 states appear somewhere and evidence highlights land on the right words.
4. All branches then `git pull origin main` (or merge main) before continuing.
5. Conflicts should only ever occur in files a part doesn't own — if that happens, the owner's version wins.

---

## 14. Demo, video and judging

| Criterion | How we win it |
|---|---|
| Innovation | Evidence on the photo for every flag; "not detected" vs "can't determine"; self-verifying extraction; family-wide verdicts; Telugu voice |
| Technical implementation | OCR + LLM token-citation grounding, deterministic engine with tests, measured accuracy on real packets, agent with tools, fallback chain |
| Real-world impact | Allergy/diabetes/Jain persona; multilingual; honest unknowns |
| UI/UX | Camera guidance, one-tap evidence, motion that explains (scan beam, verdict reveal), mobile-first |
| Completeness | Every state handled, offline/fallback paths, installable PWA, deployed link |
| Presentation | Persona story, live scan of a judge-chosen packet, accuracy numbers |

Video (≤ 3 min unless told otherwise): problem in 20 s (real packet close-up) → live scan → tap evidence → retake an unknown → Telugu voice question → "How it works" with accuracy numbers → architecture slide → close on principle "we never say safe; we show you why".

---

## 15. Global definition of done
- Runs from a clean clone on both laptops following `docs/SETUP_AND_GIT.md`.
- No paid service, no key in git, `.env.example` complete.
- Each part's checks pass; integration smoke test passes on 3 real packets.
- Works on Chrome + Edge desktop and an Android phone; iPhone works except voice input.
- README explains setup, architecture, honesty principles, accuracy results and limitations.

## 16. Top risks
| Risk | Mitigation |
|---|---|
| Gemini free-tier rate limit mid-demo | Cache by image hash; warm the cache with demo packets; Ollama fallback; second key |
| Venue Wi-Fi | Run backend + Ollama on the Mac; phone on Mac's hotspot/LAN; recorded backup video |
| OCR weak on curved/glossy labels | Capture guidance, multi-panel, region re-read, user correction |
| Hindi/Telugu text on labels | LLM reads it directly; evidence falls back to `approximate` boxes |
| Integration surprises | Frozen contract + shared fixtures + early M1 merge |
| Running out of time | Strict priority order; stretch only after M2 |
