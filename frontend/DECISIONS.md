# Part 1 — decisions where the spec was silent (one line each)

- Router: `react-router-dom` v6 (free, React 18 compatible); every route is a lazy chunk.
- Fonts: the spec's Google Fonts, self-hosted via Fontsource (same OFL files) so the PWA works offline and the browser makes no third-party requests; only the latin `wght` files plus the Devanagari/Telugu script files are declared (`src/styles/fonts.css`).
- Tailwind 3.4 (JS config) mapping colours to the CSS variables in `tokens.css` via `color-mix(... <alpha-value>)`, so opacity modifiers like `bg-conflict/15` work in both themes.
- Light theme verdict colours are darker variants (#c8382d, #a35f00, #17855a, #4d56c9) so text on them passes AA on the paper background; `--on-verdict` gives the text colour on solid badges.
- `@react-three/fiber` 8 (v9 requires React 19); `three` pinned to 0.170.x.
- `@react-three/drei` is not used: importing `RoundedBox` pulled ~50 kB gzip of drei into the hero chunk; three's own `RoundedBoxGeometry` does the same job. Re-add drei only if a later phase needs it.
- No Rollup `manualChunks`: it pulled React into the three chunk; natural splitting keeps three in `Hero3D` and lenis in `Landing`. `npm run check:chunks` verifies this by chunk content.
- i18n keys are flat and dotted (`keySeparator: false`) with `{name}` placeholders, so `shared/messages.en.json` keys and templates are copied verbatim.
- `categories.*` names are lower-case because they are interpolated mid-sentence ("this counts as peanut"); `basis.per_100g` = "100 g" because templates read "per {basis}".
- "or" joining uses `Intl.ListFormat(lang + "-IN", { type: "disjunction" })`; numbers use `Intl.NumberFormat(lang + "-IN")` (Indian digit grouping).
- `renderMessage` shows "—" for a missing param (never a raw `{placeholder}`) and falls back to English, then to the key.
- `Correction.field_path` format: dot keys + bracket indices, e.g. `ingredients[3].name`, `nutrition.rows[2].values[0].amount` (`src/lib/fieldPath.ts`).
- Mock `scan`/`recheck` return only the fixture reports whose `profile_id` was sent (no profiles → extraction only, matching the first-run rule); `?mockError=<CODE>` is read when the call starts.
- "Try the demo label" stores the fixture family as the scan's profiles without touching the user's saved profiles.
- Hero chips are positioned from the fixture's evidence boxes; the 3D camera is placed so the label face matches the DOM overlay rectangle exactly. Under 640 px the word chip morphs into its verdict tag in place (no room to stack).
- Scroll-linked values use function transforms (`useScrollRange`): Motion's accelerated scroll timelines did not clamp after the last keyframe, so chips faded back out.
- Lenis runs on the landing page only this phase (spec allows About too, but the phase rule keeps Lenis inside the landing chunk).
- Scan route is a photo-upload flow in Phase 1 so loading/error paths are exercisable; the live camera replaces it in Phase 2.
