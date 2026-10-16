# LabelLens frontend

React 18 + Vite 6 + TypeScript (strict) + Tailwind. A camera-first PWA that photographs a food label, sends it to the backend and shows every family member's verdict with the exact words on the photo behind it. Verdicts come from the backend's deterministic engine; this app only displays them.

## Local setup

Requirements: Node 22 (npm 10). Windows and macOS both work.

```bash
cp .env.example .env          # in the repo root; the frontend reads ../.env
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

`predev`/`prebuild` run two small scripts:
- `scripts/sync-shared.mjs` copies `../shared/contract.ts`, the fixtures and the English messages into `src/shared/`. Never edit `src/shared/` by hand.
- `scripts/render-poster.mjs` renders the sample label to `public/hero-poster*.webp` with sharp (only when missing; `npm run render-poster` re-renders).

### Environment (root `.env`)

| Variable | Use |
|---|---|
| `VITE_USE_MOCKS` | `true` → every API call is answered from `src/shared/fixtures` (no backend needed). Anything else → the real API. |
| `VITE_API_BASE_URL` | Leave **empty** locally: the browser calls same-origin `/api` and Vite proxies it. Set it only for deployed builds (the backend's public URL). |
| `API_PROXY_TARGET` | Where the dev/preview server proxies `/api` (default `http://localhost:8000`; on the team setup, the Mac's backend, e.g. `http://192.168.1.20:8000`). |
| `VITE_HTTPS` | `true` → self-signed HTTPS on the dev server (for camera tests on a phone over the LAN without a tunnel). |

## Mock mode and dev switches

With `VITE_USE_MOCKS=true`, these query parameters change behaviour (they survive navigation from Scan to Result):

| Query | Effect |
|---|---|
| `?mockError=RATE_LIMITED` | Every mocked POST fails with that server error code: `RATE_LIMITED`, `LLM_UNAVAILABLE`, `BAD_IMAGE`, `TOO_MANY_IMAGES`, `VALIDATION` or `INTERNAL`. |
| `?mockScenario=unreadable` | The scan comes back OCR-only, every section incomplete, every verdict unknown — the unknown-heavy result UI. |
| `?debug=1` | Calibration overlay on the camera (developer-only, untranslated). |

"Try the demo label" never needs a backend: it loads the bundled fixtures. A language switch or correction on the demo falls back to the mock recheck if `/api/recheck` fails.

## Testing on a phone

The camera needs HTTPS. Easiest path, which also checks the real production build:

```bash
npm run build
npx vite preview --port 4173              # serves dist/, proxies /api to API_PROXY_TARGET
cloudflared tunnel --url http://localhost:4173
```

Open the printed `https://….trycloudflare.com` URL on the phone. One tunnel is enough because `/api` is proxied. `*.trycloudflare.com` is already in `allowedHosts`. To install the PWA, use Chrome's "Install app" on Android, or Share → Add to Home Screen on iOS (the app shows these steps).

Alternative without a tunnel: `VITE_HTTPS=true npm run dev -- --host`, then accept the self-signed certificate on the phone.

## Deploying to Vercel

Import the repo in Vercel with:

- **Root Directory:** `frontend` (keep "Include files outside the root directory" on — the build syncs from `../shared`)
- **Framework:** Vite · **Build:** `npm run build` · **Output:** `dist` (also set in `vercel.json`)
- **Environment variables:**
  - `VITE_USE_MOCKS=false`
  - `VITE_API_BASE_URL=https://<deployed-backend>` (no trailing slash)
- **Backend side:** `CORS_ORIGINS` on the backend must include the Vercel domain (`https://<project>.vercel.app` and any preview domains you use).

`vercel.json` adds:
- the SPA rewrite (everything except `/api/*` → `index.html`);
- no-cache for `sw.js` and the manifest;
- immutable caching for `/assets/*`;
- the headers `Permissions-Policy: camera=(self), microphone=(self)`, `Referrer-Policy` and `nosniff`.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Dev server with HMR |
| `npm run build` | Type-check (`tsc -b`) + production build + service worker |
| `npm run preview` | Serve `dist/` (same host/proxy settings as dev) |
| `npm run lint` | ESLint (flat config) |
| `npm run test` | Vitest (jsdom) |
| `npm run check:chunks` | Bundle budget: entry < 250 kB gzip; three.js / Lenis only in the landing chunks |
| `npm run sync-shared` | Re-copy `../shared` into `src/shared` |
| `npm run render-poster` | Re-render the landing poster images |
| `npm run pwa-assets` | Regenerate PWA icons from `public/logo.svg` |

Before reporting a phase: `npm run build && npm run lint && npm run test && npm run check:chunks`.

## UI architecture

```
src/
  main.tsx, App.tsx      boot (lazy language load, install-prompt capture), router, LazyMotion
  routes/                Landing · Scan · Result · Profiles · About · NotFound (each lazy-loaded)
  api/                   client.ts (fetch + timeouts + error mapping) · mock.ts (fixtures) · index.ts (switch)
  store/                 zustand: scan (images, result, recheck, corrections) · profiles (IndexedDB) · ui (lang, theme)
  i18n/                  en eager, hi/te lazy; flat dotted keys; renderMessage() fills engine message_params
  components/
    landing/             hero (poster → 3D on first interaction), sections, Lenis smooth scroll
    capture/             camera, quality coaching (workers/quality.worker.ts), panel tray, upload fallback
    evidence/            photo viewer with zoom/pan, evidence outlines and chips
    verdict/             family strip, verdict cards, state badges, "why" disclosure
    label/               ingredients, nutrition, unknowns, corrections, explain sheet
    ask/ speech/         ask bar + answer sheet, voice input, read-aloud
    profiles/            sentence → parse → confirm, form editor, thresholds
    layout/ ui/          shell, header, install button, offline banner, sheets, error notices
  lib/                   pure helpers (box maths, quality checks, formatting, metrics parser…) — unit-tested
```

Performance rules:
- three.js and Lenis load only on the landing page (the 3D hero only after the first interaction);
- sheets are lazy-mounted;
- hi/te dictionaries load on demand;
- `check:chunks` enforces the budget.

## Honesty rules the UI enforces

- Only four states are shown: **Conflict**, **Check this**, **Not listed**, **Unknown** (Not detected / Can't determine). The words "safe", "healthy" and "guaranteed" never appear, and `copy.test.ts` checks this.
- Each state uses colour plus an icon plus a pattern (unknown is hatched), so states never rely on colour alone.
- Every flag links to its evidence on the photo, or says it couldn't be located.
- OCR-only results show a banner that missing items can't be confirmed.
- About shows measured accuracy only from real packets (`public/metrics.json`). Synthetic test runs are described as software tests, never shown as accuracy.
