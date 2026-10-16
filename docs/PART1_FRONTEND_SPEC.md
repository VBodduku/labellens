# Part 1 — Frontend (React PWA)

**Machine:** System A (Windows) · **Tool:** Claude Code · **Branch:** `part-1-frontend` · **Folder you own:** `frontend/` only
**Read first:** `docs/00_MASTER_SPEC.md` (whole), `shared/contract.ts`, `shared/messages.en.json`, `shared/fixtures/*`.

You build everything the user sees and touches. You work **fully against mocks** (`VITE_USE_MOCKS=true`, data from `shared/fixtures/`) until Merge 1, so you never wait for the backend.

---

## 1. Goals

1. A camera-first scan flow that gets a sharp, complete photo on the first try.
2. A result screen where **every flag can be traced to the exact words on the photo** in one tap.
3. A family-first experience: one scan, one verdict per person.
4. Telugu / Hindi / English with voice in and out.
5. A premium, motion-rich feel that **explains** (scan beam, evidence zoom, verdict reveal), not decoration. Inspired by Awwwards-level sites, but the scan and result screens must be fast and calm.

---

## 2. Stack

React 18 + Vite + TypeScript (strict) · Tailwind CSS · `motion` (Motion for React) · `@react-three/fiber` + `@react-three/drei` + `three` (landing hero only, lazy-loaded) · `lenis` (landing + about only) · `zustand` · `react-i18next` + `i18next` · `idb-keyval` · `react-zoom-pan-pinch` · `vite-plugin-pwa` · `lucide-react` · Vitest.
All free and open source. No UI kits that need licences.

---

## 3. Folder structure

```
frontend/
├── index.html
├── package.json            scripts: dev, build, preview, lint, test, sync-shared (all cross-platform)
├── vite.config.ts          envDir '..', server.host true, proxy /api -> http://localhost:8000, basic-ssl (see §11)
├── vercel.json             SPA rewrites
├── scripts/sync-shared.mjs copies ../shared/{contract.ts,messages.en.json,fixtures/*} -> src/shared/ (skips if ../shared absent)
├── public/                 icons, manifest assets, metrics.json (placeholder until Part 3 provides)
└── src/
    ├── main.tsx, App.tsx
    ├── routes/             Landing.tsx, Scan.tsx, Result.tsx, Profiles.tsx, About.tsx, NotFound.tsx
    ├── components/
    │   ├── ui/             Button, Sheet, Tabs, Chip, Badge, Toast, Skeleton, IconButton, Toggle, Slider
    │   ├── layout/         AppShell, Header, LanguageSwitcher, PageTransition
    │   ├── landing/        Hero3D (lazy), ScanBeam, ProblemSection, HowItWorks, HonestySection, CTA
    │   ├── capture/        CameraView, QualityHints, CaptureButton, PanelTray, UploadFallback, TorchToggle
    │   ├── evidence/       EvidenceViewer, EvidenceOverlay, EvidenceChip, PanelSwitcher
    │   ├── verdict/        FamilyStrip, ProfileVerdictCard, ResultCard, StateBadge, WhyDisclosure
    │   ├── label/          IngredientsList, IngredientRow, ExplainSheet, NutritionTable, ConsistencyBadge,
    │   │                   UnknownsPanel, CorrectionEditor, ExtractionMetaBadges
    │   ├── profiles/       ProfileList, ProfileEditor, RestrictionPicker, ThresholdControl,
    │   │                   SentenceInput, ParseConfirmSheet
    │   ├── ask/            AskBar, AnswerSheet, ToolTrace
    │   └── speech/         MicButton, ReadAloudButton
    ├── api/                client.ts (real), mock.ts (fixtures + delays), index.ts (switch on VITE_USE_MOCKS), errors.ts
    ├── store/              profiles.ts (persisted to IndexedDB), scan.ts, ui.ts
    ├── i18n/               index.ts, en.json, hi.json, te.json, renderMessage.ts
    ├── lib/                speech.ts, imageProcessing.ts, boxMath.ts, format.ts, ids.ts, featureDetect.ts
    ├── workers/            quality.worker.ts
    ├── shared/             (synced copies — do not edit by hand)
    └── styles/             tokens.css, globals.css
```

**Naming:** components `PascalCase.tsx`, everything else `camelCase.ts`. Import paths must match file-name case exactly (Windows and macOS ignore case; Vercel's Linux build does not).

---

## 4. Design direction — "Lens"

**Idea:** a precision instrument. Dark, calm surfaces; the label photo is the hero; one recurring signature motif — the **scan beam** (a thin horizontal line of light with a soft glow) — appears in the 3D hero, the camera view, the analysing state and the evidence highlight. Everything else stays quiet so the evidence pops.

**Tokens (`styles/tokens.css`, CSS variables, used through Tailwind config):**
- Surfaces: `--bg #0B0D12`, `--surface #12151C`, `--surface-2 #1A1F29`, `--line #262C38`, `--text #EEF1F6`, `--text-dim #9AA3B2`. Provide a light theme (`--bg #F6F4EF` paper-warm, etc.) via `[data-theme="light"]` and default to system preference — shops are bright and outdoor glare is real.
- Accent: `--beam #7CF5FF` (cyan) → `--beam-2 #A98BFF` gradient for the beam and primary actions.
- **Verdict states** (always icon + text + pattern, never colour alone):
  - Conflict `--conflict #FF5A4E`, icon octagon-X, solid fill.
  - Check this (`possible`) `--possible #FFB547`, icon triangle-!, solid fill.
  - Not listed `--not-listed #3DDC97`, icon circle-check, outline.
  - Unknown `--unknown #9AA4FF`, icon dashed circle-?, **diagonal hatch pattern** background; sub-label "Not detected" or "Can't determine".
- Type: display **Bricolage Grotesque** (Google Fonts), body **Manrope**, evidence/label text **JetBrains Mono**; **Noto Sans Telugu** and **Noto Sans Devanagari** for te/hi (load only the subsets needed, `font-display: swap`). Check Telugu line-height — it needs ~1.6.
- Radius 14 px cards, 999 px chips. Elevation via subtle inner borders, not heavy shadows.
- Motion tokens: `--ease-out cubic-bezier(.2,.8,.2,1)`, durations 160 / 260 / 420 ms. Only animate `transform` and `opacity`. `prefers-reduced-motion` → crossfades only, no beam sweep, no 3D auto-rotation.

If a frontend-design skill or plugin is available in your Claude Code setup, use it for craft details, but this section's tokens and motif win on any conflict.

---

## 5. Screens

### 5.1 Landing `/`
- **Hero (R3F, lazy chunk):** a floating packet (rounded box) with the label texture from `src/shared/fixtures/sample_label.svg`. The scan beam sweeps across it; on scroll (Lenis + scroll progress), words lift off the label as glowing chips that snap into verdict tags ("Peanuts → Conflict for Aarav"). Mouse/touch parallax. DPR capped at 1.5 on mobile; static poster image fallback while the chunk loads and for reduced motion / no WebGL.
- Sections (scroll-triggered, not overdone): the problem (3 pains, short), how it works (5-step pipeline with the beam travelling between steps), the honesty principle (the 4 states explained with tiny examples), the family idea, CTA "Scan a label" + "Try the demo label" (loads the fixture result without a camera — judges love a zero-friction demo).
- Header: logo, language switcher (EN / हिं / తె), Profiles, How it works, Install button (when installable).

### 5.2 Scan `/scan`
- Full-screen camera (`getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } } })`). Torch toggle if `track.getCapabilities().torch`.
- Framing guide (rounded rectangle with corner brackets) + the beam sweeping slowly inside it.
- **Quality worker** (`workers/quality.worker.ts`): ~6–8 times per second, the main thread draws the video frame to an `OffscreenCanvas`/canvas at 320 px wide and sends `ImageData` (transfer the buffer). Worker computes:
  - grayscale; **blur** = variance of 3×3 Laplacian; **glare** = fraction of pixels with luma > 245; **brightness** = mean luma; **motion** = mean absolute difference vs previous frame.
  - Returns metrics + issues. Thresholds live in one constants file and **must be calibrated on the real phone** (add a hidden `?debug=1` overlay printing live values).
- Hint pill shows the single most important issue using `quality.*` message keys (translated).
- **Auto-capture:** when all checks pass continuously for 700 ms → grab a full-resolution frame from the video into a canvas → shutter animation + `navigator.vibrate?.(30)`. Manual shutter always available. A ring around the shutter fills while the "good" window accumulates.
- **Panel tray:** up to 3 captured panels with thumbnails, a panel label (Front / Back / Side, user can change), retake, delete. Hint text: "Add the back if the ingredients wrap around."
- Upload fallback (`<input type="file" accept="image/*" capture="environment" multiple>`), and full permission-denied / no-camera states with clear instructions.
- Before upload, `lib/imageProcessing.ts` downsizes to ≤ 2000 px long side, JPEG quality 0.9, and corrects EXIF orientation (draw via `createImageBitmap(file, { imageOrientation: "from-image" })`).
- "Analyse" → navigates to the analysing state.

### 5.3 Analysing state (inside Result route while loading)
- The captured photo with the beam sweeping over it and **honest stage text** driven by elapsed time: "Reading the text…" → "Understanding the label…" → "Double-checking unclear parts…" → "Checking for {n} family members…". No fake percentage bar. Cancel button. On error: specific message per `error_code`, retry, and "edit photos".

### 5.4 Result `/result`
Mobile: photo viewer on top (≈ 45 % height, collapsible), content below. Desktop ≥ 1024 px: photo left (sticky), content right.

- **EvidenceViewer:** image (object URL of the uploaded panel) inside `react-zoom-pan-pinch`; an absolutely positioned SVG overlay with `viewBox="0 0 1 1" preserveAspectRatio="none"` exactly covering the image draws boxes from `Evidence.box` (normalised). Panel switcher if several images.
  - **Focus behaviour:** tapping any evidence chip anywhere → switch to that panel → animate zoom/pan so the box fills ~60 % of the viewer → dim everything outside it with an SVG mask → pulse the outline in the result's state colour twice → screen-reader announces the text.
  - `approximate` evidence draws a dashed box; `unverified` shows a chip "Couldn't locate on photo" instead of a box.
- **FamilyStrip:** horizontal profile chips (avatar colour, name, overall state badge). Selected profile uses a `layoutId` underline. Default selection = worst overall.
- **ProfileVerdictCard:** overall state headline (translated `overall.*`), the grounded summary (`report.summary` if `summary_lang` matches, else a template summary built from message keys), read-aloud buttons (short / full).
- **ResultCard list** sorted worst-first (`VERDICT_ORDER`): StateBadge, restriction label, `renderMessage(message_key, message_params, lang)`, evidence chips, a "Why?" disclosure listing `matches` (with source: "From our ingredient database", "Label allergen statement", "Veg mark", "Nutrition table", or "AI interpretation — please verify"), confidence as a subtle meter.
- Tabs below: **Verdicts | Ingredients | Nutrition | Couldn't read**.
  - *Ingredients:* every ingredient with origin icon, category tags from `annotations`, readability marker, tap → ExplainSheet (`/api/explain`), pencil → CorrectionEditor.
  - *Nutrition:* table with toggle **Per 100 g · Per serving · Whole pack** (from `nutrition_analysis.per_100` / extraction values / `per_pack`), ConsistencyBadge (`consistency.message_key`, suspect rows highlighted), each value editable, `nutrition.serving_small` note when present.
  - *Couldn't read:* each `UnknownItem` with its message, a mini-thumbnail of the region, and **"Retake this area"** → camera opens for that panel, the new photo replaces it, and the scan reruns.
- **ExtractionMetaBadges:** "Double-checked 1 unclear area" from `meta.retries`; "On-device AI" when `provider === "ollama"`; "Limited mode (text only)" when `provider === "ocr_only"`; cached indicator hidden.
- **Corrections:** saving a change appends a `Correction`, patches the extraction locally, calls `/api/recheck`, and animates any verdict whose state changed (badge morph + short highlight). Corrected values show an "Edited" tag.
- **AskBar** (sticky bottom): text field + MicButton + send. Answer opens AnswerSheet: answer text, ReadAloud, evidence chips (same focus behaviour), ToolTrace chips ("Checked Thatha's profile", "Searched the label for 'sugar'") from `tool_calls`, and a refusal style when `grounded === false`.

### 5.5 Profiles `/profiles`
- List of family members (colour avatar, name, restriction chips). Add / edit / delete. Persisted in IndexedDB (`idb-keyval`) — no accounts.
- **ProfileEditor:** name, colour, RestrictionPicker grouped by `kind` from the catalog (`/api/catalog`, mock = `catalog.json`), each restriction with a severity toggle ("Strict — allergy" / "Preference") and, for `needs_threshold`, a ThresholdControl (slider + number, default from catalog with its `source_note` shown).
- **"Describe your family"** SentenceInput (text + mic) → `/api/profile/parse` → **ParseConfirmSheet** listing proposed profiles and restrictions, each with the phrase it came from (`source_text`), warnings and `unparsed` phrases highlighted. Nothing is saved until the user confirms; every item is editable/removable.
- First-run: if no profiles, the scan still works and shows extraction only, with a gentle prompt to add family members. The "Try the demo label" path uses `profiles.json`.

### 5.6 How it works `/about`
Pipeline explained visually, the four states, what we never claim, privacy, limitations, and **accuracy** read from `public/metrics.json` (Part 3 produces it near the end; ship a placeholder with `"status": "pending"` and render a tasteful "Measured results coming soon" until then).

---

## 6. State

- `store/profiles.ts` — `profiles: Profile[]`, CRUD, `hydrate()` from IndexedDB on start.
- `store/scan.ts` — `panels: { file: Blob; url: string; hint: PanelHint }[]`, `result: ScanResult | null`, `status`, `error`, `corrections`, actions `analyse()`, `recheck()`, `retakePanel(i)`. Keep the last result in IndexedDB so a refresh doesn't lose it (object URLs are recreated from stored blobs).
- `store/ui.ts` — `lang` (persisted), `theme`, `selectedProfileId`, `focusedEvidence`, `voiceRate`.

---

## 7. API layer

`api/index.ts` exports `{ health, catalog, scan, recheck, ask, parseProfile, explain }` with the types from `src/shared/contract.ts`.
- Real client: `fetch` with `AbortController` timeouts (scan 60 s, others 20 s), parses `ErrorResponse`, throws typed `ApiError`. Base URL = `import.meta.env.VITE_API_BASE_URL || ""` (empty → same-origin `/api`, proxied by Vite in dev).
- Mock client: returns fixtures with realistic delays (scan 2.5 s; ask 1.2 s), simulates one error path when `?mockError=RATE_LIMITED` is in the URL, and for `recheck` echoes the fixture with the corrections applied to the extraction (verdicts unchanged in mock mode — that's fine).
- `scan()` builds `FormData`: append each panel as `images` in order, `profiles` as JSON string, `lang`, `panel_hints` JSON.

---

## 8. Internationalisation

- `i18n/en.json` = UI strings + **every key from `shared/messages.en.json`** except keys starting with `_` (copy verbatim; add a test that fails if any key is missing in en/hi/te). Also add `categories.<id>` for every id in `CATEGORIES`, `nutrients.<key>` for every `NUTRIENT_KEYS` entry, and `basis.<id>`.
- `hi.json`, `te.json`: full translations. Draft them yourself, mark the file header "NEEDS HUMAN REVIEW", and list the 20 most important strings in `frontend/NOTES_FOR_OTHERS.md` for native speakers on the team to check.
- `renderMessage(key, params, lang)`: interpolates `{placeholders}`. **Param conventions** (from the engine): `category` is one category id or several joined by `|` → translate each via `categories.<id>` and join with the locale's "or"; `nutrient` is a nutrient key (`total_sugars_g`) → `nutrients.<key>`; `basis` is a basis id (`per_100g`) → `basis.<id>`; `term`/`item` are label text → show as-is (original language, mono font). Numbers formatted with `Intl.NumberFormat(lang + "-IN")`.
- Language switch re-renders instantly; summaries in another language need `/api/recheck` with the new `lang` (show the template summary meanwhile).
- `<html lang>` updates; Indic fonts applied via `:lang(te)` / `:lang(hi)`.

---

## 9. Speech

`lib/speech.ts`
- **Input:** `window.SpeechRecognition || window.webkitSpeechRecognition`. Language map `en → en-IN`, `hi → hi-IN`, `te → te-IN`. Interim results shown live in the field; auto-stop after ~2 s of silence; clear errors for `not-allowed`, `no-speech`, `network`. If unsupported (common on iOS), hide the mic and show a one-line note in the help sheet — typing always works.
- **Output:** `speechSynthesis`; wait for `voiceschanged`; pick the best voice whose `lang` starts with the target language; if none exists for hi/te on this device, show "No {language} voice on this device" and offer English. Short mode = overall line + first result; Full mode = summary + every result. Stop button; never overlap utterances; respect the user's rate setting.
- Test on the demo laptop **and** the demo phone early — available voices differ per OS.

---

## 10. PWA

`vite-plugin-pwa`: manifest (name "LabelLens", theme colour, maskable icons generated from an SVG logo), app-shell precache, **no caching of `/api/*`**. Install button using `beforeinstallprompt` (Android/desktop Chrome/Edge); on iOS show an instruction sheet ("Share → Add to Home Screen"). Must work full-screen (`display: standalone`) including camera.

---

## 11. Running on the phone (camera needs HTTPS)

Browsers only allow camera access on HTTPS or `localhost`. For the phone during development and the live demo:
1. **Preferred:** `cloudflared tunnel --url http://localhost:5173` on the Mac → free HTTPS URL; Vite proxies `/api` to the local backend, so one tunnel is enough. Add the tunnel host to `server.allowedHosts`.
2. Fallback: `@vitejs/plugin-basic-ssl` (self-signed) enabled with `VITE_HTTPS=true`; open `https://<laptop-LAN-IP>:5173` on the phone and accept the warning.
Production: Vercel (HTTPS) → backend on HF Spaces (HTTPS).

---

## 12. Quality bar and done criteria

- `npm run build`, `npm run lint`, `npm run test` pass on Windows. No TypeScript `any` in app code except at the speech API boundary.
- Every screen: loading, empty, error states; keyboard focus visible; no horizontal scroll at 360 px; tap targets ≥ 44 px.
- Scan and result routes do **not** import Three.js or Lenis (check the build output chunk sizes; main bundle < 250 kB gzip).
- Lighthouse mobile on landing: Performance ≥ 80, Accessibility ≥ 95.
- With mocks: the full demo story in master spec §2 works end to end, including evidence focus on "Peanuts (22%)", the sodium "Can't determine" with retake, and the Telugu UI.
- Works in Chrome and Edge (desktop + Android). On iPhone everything except voice input.

## 13. Do not
- Do not touch anything outside `frontend/`. Shared copies in `src/shared/` are overwritten by `sync-shared`.
- Do not hard-code verdicts or say "safe/healthy" anywhere.
- Do not call any external API from the browser except our backend (no keys in the frontend).
- Do not add paid fonts, icons, or libraries.
