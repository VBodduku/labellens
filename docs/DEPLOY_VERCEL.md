# Deploying LabelLens (Vercel + Render)

LabelLens has two parts to deploy:

| Part | Where | Why |
|---|---|---|
| **Frontend** (`frontend/`, the app people open) | **Vercel**, free Hobby plan | A static PWA: fast, HTTPS (the camera needs it), free. |
| **Backend** (`backend/` + `engine/` + `shared/`) | **Render**, free web service, Docker | It runs OCR models in a ~1.1 GB Docker image, and a scan can take 15–40 s. That doesn't fit Vercel's serverless functions. |

Order: **backend first** (you need its URL), then the frontend, then connect them. Time: about 30 minutes, most
of it waiting for the first Docker build.

You need: a GitHub account with access to the `labellens` repository, and a Gemini API key from
[Google AI Studio](https://aistudio.google.com/). Don't put keys in any file in the repository. They go only into the
dashboards below.

---

## Part A — Backend on Render

1. Sign up at <https://render.com> with GitHub, and allow Render to access the `labellens` repository.
2. In the dashboard, click **New → Blueprint** and pick the repository. Render reads `render.yaml` at the repo root
   (Docker, free plan, health check `/api/catalog`, `ENGINE_MODE=real`, `OCR_WORKERS=1`).
3. Render asks for the secret values (the blueprint also sets `OCR_TIMEOUT_S=100` and `SCAN_BUDGET_S=150`, because
   the free plan's 0.1 CPU needs about 30 s just to read one photo):
   - `GEMINI_API_KEY`: your key.
   - `GEMINI_API_KEY_BACKUP`: a second key, or leave it empty.
   - `CORS_ORIGINS`: leave as `http://localhost:5173` for now. You'll add the Vercel URL in Part C.
4. Click **Apply**. The first build takes 5–10 minutes.
5. When it shows **Live**, copy the service URL, e.g. `https://labellens-api.onrender.com`.
6. Check it in a browser: `https://labellens-api.onrender.com/api/health` should show
   `"status": "ok"`, `"engine_mode": "real"`, `"gemini": true` (`"ollama": false` is expected; there is no Ollama on Render).

Manual setup without the Blueprint, and troubleshooting: [`backend/README.md`](../backend/README.md) → "Deploy to
Render".

## Part B — Frontend on Vercel

1. Sign up at <https://vercel.com> with GitHub.
2. Click **Add New… → Project**, and **Import** the `labellens` repository.
3. On the **Configure Project** screen:

   | Setting | Value |
   |---|---|
   | **Framework Preset** | Vite |
   | **Root Directory** | `frontend` (click **Edit** and choose the folder) |
   | **Build Command** | `npm run build` (default; also in `frontend/vercel.json`) |
   | **Output Directory** | `dist` (default) |
   | **Install Command** | `npm install` (default) |

4. Open **Environment Variables** and add:

   | Name | Value |
   |---|---|
   | `VITE_API_BASE_URL` | the Render URL from Part A, e.g. `https://labellens-api.onrender.com`, with **no trailing slash** |
   | `VITE_USE_MOCKS` | `false` |
   | `VITE_SCAN_TIMEOUT_S` | `180` (the app waits this long for a scan; the free backend needs 1–2 minutes) |

5. Click **Deploy**. The build takes about 1–2 minutes.
6. After deploying, open **Settings → General → Node.js Version** and choose **22.x** (the app needs Node 22 or
   newer). If you changed it, redeploy: **Deployments → ⋯ → Redeploy**.
7. Copy the production URL, e.g. `https://labellens.vercel.app`.

Notes:
- `VITE_*` values are built into the app. **After changing one, redeploy**, or the old value stays.
- `frontend/vercel.json` already sets the routing (every page loads the app), caching, and a
  `Permissions-Policy` that allows the camera and microphone on this site.
- The build uses committed copies of `shared/` (`frontend/src/shared/`). It works whether or not Vercel includes
  files outside the `frontend` folder.

## Part C — Connect the two

1. In Render, open the backend service → **Environment** → `CORS_ORIGINS`, and set it to the Vercel URL, e.g.

   ```
   https://labellens.vercel.app,http://localhost:5173
   ```

   (comma-separated, no spaces, no trailing slashes). If you also use Vercel preview links, add each one you need.
2. **Save Changes**. Render restarts the service (about a minute).

## Part D — Check that it works

1. Open the backend `…/api/health` once, to wake it up (free services sleep after 15 minutes idle; waking takes about a
   minute).
2. Open the Vercel URL on your phone.
3. **Try the demo label:** the result opens with Aarav, Thatha and Lakshmi.
4. Go to the **Ingredients** tab, edit an ingredient, and save. "Rechecking…" then an updated verdict means the frontend
   reached the backend.
5. **Scan a label:** allow the camera, take a photo, tap **Analyse**. A result without the "Basic reading only" banner
   means Gemini is working on the server.
6. Install it: in Chrome, **Install app**. On iPhone, **Share → Add to Home Screen**.

## Troubleshooting

| What you see | Cause and fix |
|---|---|
| "Can't reach LabelLens" on scan or recheck | `VITE_API_BASE_URL` is wrong, missing, or has a trailing slash. Fix it in Vercel and **redeploy**. Or the backend is asleep: open `/api/health` and wait. |
| Browser console: *blocked by CORS policy* | The Vercel URL is missing from `CORS_ORIGINS` on Render, or doesn't match exactly (https, no trailing slash). |
| "Basic reading only" on every scan | Gemini isn't working on the server. Check `/api/health` → `"gemini"`. If false: the key is missing or refused (create a new key in a new AI Studio project), or the free quota is used up (add `GEMINI_API_KEY_BACKUP`). |
| "We couldn't use this photo" on a sharp photo, about 30 s after Analyse | The free plan's 0.1 CPU ran out of time reading the photo. On Render set `OCR_TIMEOUT_S=100` and `SCAN_BUDGET_S=150`; on Vercel set `VITE_SCAN_TIMEOUT_S=180` and redeploy. |
| Scans time out on Render | First scan after waking, or a very large photo. Try again. Check the three time limits above and `OCR_WORKERS=1`. |
| Render "Out of memory" (Events tab) | `OCR_WORKERS` must be `1` on the free plan. |
| Camera doesn't open | Use the `https://` Vercel URL, not a preview iframe; allow the camera in the browser's site settings. **Upload a photo** always works. |
| The old version keeps loading | The app is a PWA and caches itself. Close and reopen it, or clear the site data. |

## A demo link with no backend (optional)

For a link that always works, even when the backend or Gemini is down, create a **second** Vercel project from the
same repository with `VITE_USE_MOCKS=true` (and no `VITE_API_BASE_URL`). It runs entirely on the bundled demo data:
the demo label, its verdicts, evidence zoom, "Couldn't read" and language switching all work. Live scanning doesn't,
and edits or pack confirmations are saved but don't change verdicts, because there is no engine. Label it clearly as
the offline demo.
