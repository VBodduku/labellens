# Notes from Part 1 (frontend) for other parts / main

## Requests for `main` (humans decide)
1. **`.env.example`: set `VITE_API_BASE_URL=` (empty).** With `http://localhost:8000`, a phone or a cloudflared tunnel calls *its own* localhost and every request fails. Empty means same-origin `/api`, which Vite proxies to `localhost:8000` in dev (and works through one tunnel). Set it to the deployed backend URL only for the Vercel build.
2. **Fixture summary wording (`shared/fixtures/scan_result.json`, Lakshmi):** "Probably fine for Lakshmi's sesame allergy…" reads as reassurance. Suggest Part 2's summary prompt avoid "fine/okay" phrasing, e.g. "Sesame isn't listed. For Jain rules, 'natural flavours' doesn't say what it is made from."

## For Part 2 (backend)
- `Correction.field_path` values the frontend sends look like `ingredients[3].name` and `nutrition.rows[2].values[0].amount` (dot keys, bracket indices). `/api/recheck` receives the extraction with corrections already applied and listed in `user_corrections`.
- Scan uploads name files `panel_<i>.jpg|png` in order; `panel_hints` is a JSON array aligned with `images`.
- The frontend treats unknown `error_code` values as `INTERNAL`; please stick to the six codes in master spec §6 and send `retry_after_s` with `RATE_LIMITED`.

## For native speakers (Phase 3)
`src/i18n/hi.json` and `te.json` are English placeholders this phase (marked NEEDS HUMAN REVIEW). The 20 strings to review first will be listed here when the drafts land in Phase 3.
