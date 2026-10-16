# Part 1 — Frontend · phase prompts (System A, Claude Code, branch `part-1-frontend`)

Paste one phase at a time. Wait for the PHASE REPORT, verify it yourself (2 minutes), then paste the next one.
Times are % of total hackathon time (master spec §12).

---

## Phase 1 · Foundation + landing (0–25 %)

```
You are building Part 1 (frontend) of LabelLens. First read CLAUDE.md, then docs/00_MASTER_SPEC.md completely, then docs/PART1_FRONTEND_SPEC.md completely, then shared/contract.ts, shared/messages.en.json and the files in shared/fixtures/ (open sample_label.svg and scan_result.json). Confirm you are on branch part-1-frontend. You may only write inside frontend/.

Goal of this phase: a solid, premium foundation and a finished landing page, all running on mocks.

Do:
1. Scaffold frontend/ with Vite + React 18 + TypeScript strict. Install the stack from spec §2. Set up Tailwind wired to CSS variables in src/styles/tokens.css exactly as spec §4 (dark + light themes, verdict state colours, motion tokens). Load the fonts from spec §4 (incl. Noto Sans Telugu / Devanagari).
2. Create the folder structure from spec §3. Add scripts/sync-shared.mjs (cross-platform Node script, skips gracefully if ../shared is missing) and run it from predev/prebuild; commit the synced copies in src/shared/.
3. vite.config.ts: envDir '..', server.host true, proxy /api -> http://localhost:8000, optional basic-ssl when VITE_HTTPS=true, allowedHosts for *.trycloudflare.com.
4. API layer (spec §7): typed real client + mock client from fixtures with realistic delays + switch on VITE_USE_MOCKS + ApiError handling (?mockError=RATE_LIMITED works).
5. Stores (spec §6) with profiles persisted to IndexedDB. i18n setup with en.json complete (UI strings + every non-underscore key of messages.en.json + categories.*, nutrients.*, basis.*); hi.json/te.json may be English placeholders for now but must contain every key; add the "all keys present" test. renderMessage() with the param conventions from spec §8 + unit tests.
6. App shell: router (Landing, Scan, Result, Profiles, About, NotFound), header with language switcher (EN / हिं / తె) and theme toggle, AnimatePresence page transitions, reduced-motion support.
7. Landing page (spec §5.1) finished to a high standard: lazy-loaded R3F hero with the packet using sample_label.svg as its texture and the sweeping scan beam, word chips that lift into verdict tags on scroll, the four short sections, CTA buttons. "Try the demo label" loads the fixture into the scan store and navigates to /result (a simple placeholder result view is fine this phase). Static poster fallback for no-WebGL / reduced motion. Must look excellent at 390 px and 1440 px.
8. vercel.json SPA rewrites; basic PWA manifest; ESLint + Vitest configured; DECISIONS.md and NOTES_FOR_OTHERS.md created.

Constraints: free libraries only; Three.js and Lenis must only be in the landing chunk; no "safe" wording anywhere.
Done when: npm run build, npm run lint and npm run test pass; the landing page works on Chrome and Edge; you have committed in small steps and pushed (git push origin HEAD). Finish with the PHASE 1 REPORT format from CLAUDE.md, including the bundle sizes from the build output.
```

---

## Phase 2 · Capture flow + result screen with evidence (25–55 %)

```
Phase 2 for Part 1. Re-read docs/PART1_FRONTEND_SPEC.md sections 5.2, 5.3, 5.4, 6, 7 before starting. Keep using mocks.

Goal: the two screens that win the demo — a camera that gets a sharp photo first time, and a result screen where every flag is traceable to the words on the photo.

Do:
1. Scan route (§5.2): camera with environment facing mode and torch toggle, framing guide with the beam, the quality Web Worker (blur = Laplacian variance, glare, brightness, motion) at ~6–8 fps on a 320 px frame, hint pill using quality.* messages, auto-capture after 700 ms of continuous "good" with a filling ring + shutter animation + vibrate, manual shutter, panel tray (max 3, label Front/Back/Side, retake, delete), upload fallback, permission-denied and no-camera states. Add a ?debug=1 overlay that prints live metric values so we can calibrate thresholds on the real phone. Image processing per §5.2 (≤2000 px, JPEG 0.9, EXIF orientation).
2. Analysing state (§5.3) with honest staged text, cancel, and per-error_code messages with retry.
3. Result route (§5.4) complete:
   - EvidenceViewer: zoom/pan/pinch, SVG overlay with normalised boxes, panel switcher, verified = solid box, approximate = dashed, unverified = "Couldn't locate on photo" chip. Focus behaviour: tapping any evidence chip anywhere animates zoom/pan to the box, masks the rest, pulses the outline in the state colour, announces the text for screen readers.
   - FamilyStrip with layoutId selection (default = worst overall), ProfileVerdictCard (template summary fallback when summary_lang ≠ lang), ResultCards sorted worst-first with StateBadge (icon + text + pattern), evidence chips, "Why?" disclosure listing matches with their source, confidence meter.
   - Tabs: Verdicts / Ingredients (annotations, origin icons, readability) / Nutrition (per 100 g · per serving · whole pack toggle, ConsistencyBadge, suspect rows) / Couldn't read (UnknownItems with region thumbnail + "Retake this area" that reopens the camera for that panel and reruns the scan).
   - ExtractionMetaBadges (double-checked, on-device AI, limited mode).
   - CorrectionEditor for ingredient names and nutrient values → Correction → /api/recheck (mock) → animate any verdict whose state changes; "Edited" tags.
4. Desktop two-column layout ≥1024 px; mobile layout per spec. Motion: verdict reveal stagger, badge morphs, reduced-motion fallbacks.
5. Unit tests for boxMath (normalised box → zoom transform), quality metric functions (pure versions), sorting, renderMessage edge cases.

Verify against the demo story in master spec §2 using the fixture: tapping "Peanuts (22%)" evidence must land exactly on those words in sample_label.svg; Thatha's sodium shows "Can't determine" with a retake button.
Done when: build/lint/test pass, the demo story works on a real Android phone (use the cloudflared HTTPS link or basic-ssl, spec §11), committed and pushed. PHASE 2 REPORT, including the calibrated quality thresholds you chose and the phone you tested on.
```

---

## ⏸ Merge 1 (≈55 %) — humans
Follow docs/SETUP_AND_GIT.md "Merge 1". After main is merged, on System A:
`git fetch origin && git merge origin/main && npm --prefix frontend run sync-shared` then continue.

---

## Phase 3 · Family profiles, languages, voice, ask (55–80 %)

```
Phase 3 for Part 1. main has been merged into this branch; run npm run sync-shared first and check whether shared/ changed (contract version). Re-read spec sections 5.4 (AskBar), 5.5, 8, 9.

Goal: one scan answers for the whole family, in their language, by voice.

Do:
1. Profiles route (§5.5): list, ProfileEditor with RestrictionPicker grouped by kind from /api/catalog, severity toggle per restriction, ThresholdControl with catalog default and its source_note, colour avatars, IndexedDB persistence. "Describe your family" SentenceInput (text + mic) → /api/profile/parse → ParseConfirmSheet showing each proposed profile/restriction with its source_text, warnings and unparsed phrases; nothing saved until confirmed; everything editable. First-run prompt when there are no profiles.
2. Results use the saved profiles for real scans; the demo label path keeps using fixtures/profiles.json.
3. Internationalisation (§8): complete hi.json and te.json translations of every key (mark the files "NEEDS HUMAN REVIEW"); category/nutrient/basis param translation; locale-aware "or" joining and number formatting; <html lang>; Indic fonts and line-height; language switch triggers /api/recheck with the new lang for summaries (template summary shown meanwhile). Write the 20 most important strings for native-speaker review into NOTES_FOR_OTHERS.md.
4. Speech (§9): MicButton with en-IN / hi-IN / te-IN recognition, interim text, silence auto-stop, error states, hidden when unsupported; ReadAloudButton with short/full modes, voice selection by language, "no voice for this language" fallback, stop, rate setting.
5. AskBar + AnswerSheet: text + mic, answer with read-aloud, evidence chips using the same focus behaviour, ToolTrace chips from tool_calls in plain language, refusal styling when grounded=false.
6. ExplainSheet for ingredients via /api/explain (show source "From our database" vs "AI explanation").
7. Switch to the real backend: set VITE_USE_MOCKS=false in .env, point VITE_API_BASE_URL at the Mac's backend (http://<mac-LAN-IP>:8000) or use the integration setup the humans give you. Fix every integration problem on our side; anything that is a backend/contract issue goes to NOTES_FOR_OTHERS.md and the report.

Done when: build/lint/test pass; with the real backend a family of 3 profiles gets correct cards for 3 real packets; the UI works fully in Telugu and Hindi; voice input works in Chrome/Edge on Android; committed and pushed. PHASE 3 REPORT.
```

---

## Phase 4 · Polish, performance, PWA, ship (80–100 %)

```
Phase 4 for Part 1 — feature freeze. No new features; make everything feel finished.

Do:
1. PWA (§10): icons (maskable) generated from an SVG logo, manifest, app-shell precache, no /api caching, install button (beforeinstallprompt) and the iOS "Add to Home Screen" sheet; verify standalone mode keeps the camera working.
2. Performance: confirm scan/result routes don't load three/lenis; main bundle < 250 kB gzip; lazy-load heavy sheets; image object URLs revoked; no layout shift on result load. Lighthouse mobile on landing: Performance ≥ 80, Accessibility ≥ 95 — fix until met.
3. Accessibility: focus order, visible focus, aria labels on overlay hotspots and badges, colour-independent states, contrast AA in both themes, reduced motion everywhere.
4. Error/empty-state audit of every screen: offline, RATE_LIMITED (with retry_after), LLM_UNAVAILABLE, BAD_IMAGE, TOO_MANY_IMAGES, camera denied, no profiles, unknown-heavy results.
5. About page (§5.6) with metrics from public/metrics.json (the humans will copy engine/eval/reports/metrics.json there; render "pending" gracefully until then).
6. Mobile QA at 360/390/430 px and desktop 1280/1440 in Chrome and Edge; iPhone check (everything except voice input). Fix every issue found.
7. Deploy config for Vercel (root directory frontend, build command, env vars) documented in frontend/README.md along with local setup, mock mode, phone testing and the architecture of the UI.
8. Make sure "Try the demo label" works with no backend at all (fixtures) — it is our insurance during judging.

Done when: all checks pass, deployed preview URL works against the deployed backend, committed and pushed. PHASE 4 REPORT with Lighthouse scores and bundle sizes.
```

---

## Stretch (only if humans say so after Merge 2)

```
Stretch for Part 1: two-product comparison. Add a "Compare" action on the result screen that lets the user scan a second product, then shows a side-by-side view per family member: each product's overall state, per-100 g nutrient comparison (with protein per 100 kcal and sugar per 10 g protein), and front-of-pack claims next to the back-label evidence that supports or contradicts them (use extraction.claims). Never declare a "winner" when either product has unknowns for a relevant check — say the comparison is incomplete. Reuse existing components; add no new dependencies. If the backend provides no claim-check endpoint, compute the comparison client-side from the two ScanResults. PHASE REPORT when done.
```
