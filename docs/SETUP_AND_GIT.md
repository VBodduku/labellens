# Setup, Git and merge guide (for the humans)

**System A** = Windows laptop, GitHub **account A** (repo owner), Claude Code → Part 1 (`frontend/`).
**System B** = Mac, GitHub **account B** (collaborator), Claude Code → Part 2 (`backend/`) and Codex → Part 3 (`engine/`), each in its own **git worktree** folder. The Mac is also the Ollama host and the live-demo machine.

---

## Phase 0 — first 15 minutes (do it in this order)

### 0.1 System A: create the repo with this kit as the first commit
```bash
# unzip the kit so you have a folder named labellens/ containing CLAUDE.md, docs/, shared/ ...
cd labellens
git config --global core.autocrlf false        # .gitattributes handles line endings
git init -b main
git add -A
git commit -m "Kickoff: specs, prompts, frozen contract, fixtures"
gh auth status                                  # must show account A
gh repo create labellens --private --source=. --push
git branch part-1-frontend
git branch part-2-backend
git branch part-3-engine
git push -u origin part-1-frontend part-2-backend part-3-engine
git switch part-1-frontend
```
Add account B as a collaborator: GitHub → repo → Settings → Collaborators → Add people (or `gh api -X PUT repos/<A>/labellens/collaborators/<B> -f permission=push`). Account B accepts the e-mail/GitHub invite.

> Deliverable is a GitHub link: make the repo **public** before submission (Settings → Danger zone → Change visibility), after checking no `.env` was ever committed.

### 0.2 System B: clone once, then two worktrees
```bash
gh auth status                                  # must show account B
git clone https://github.com/<A>/labellens.git labellens        # stays on main: used for merges + integration runs
cd labellens
git fetch origin
git worktree add --track -b part-2-backend ../labellens-part2 origin/part-2-backend
git worktree add --track -b part-3-engine  ../labellens-part3 origin/part-3-engine
git worktree list
```
Result:
```
labellens/          main            (integration, demo)
labellens-part2/    part-2-backend  → open Claude Code here:  cd ../labellens-part2 && claude
labellens-part3/    part-3-engine   → open Codex here:        cd ../labellens-part3 && codex
```
Never run both tools in the same folder. Never `git switch` inside a worktree.

### 0.3 Environment files (never committed)
- Each folder that runs code needs its own `.env` at its root: `cp .env.example .env`, then fill `GEMINI_API_KEY` (and `GEMINI_API_KEY_BACKUP` from a second Google account).
  - System A `labellens/.env`: only `VITE_*` values matter (`VITE_USE_MOCKS=true`).
  - System B `labellens-part2/.env`: backend values, `ENGINE_MODE=stub`.
  - System B `labellens/.env` (integration): `ENGINE_MODE=real`, `VITE_USE_MOCKS=false`.
- Windows tip: `copy .env.example .env`.

### 0.4 Python on the Mac (each worktree has its own venv)
```bash
cd ../labellens-part2 && python3 -m venv .venv && source .venv/bin/activate && pip install -U pip
cd ../labellens-part3 && python3 -m venv .venv && source .venv/bin/activate && pip install -U pip pydantic rapidfuzz pytest
```
(Windows activation, if ever needed: `.venv\Scripts\activate`.)

### 0.5 Ollama on the Mac
```bash
ollama pull gemma3:4b          # vision-capable; choose a bigger model only if RAM allows (16 GB+ → try qwen2.5vl:7b)
ollama run gemma3:4b "Reply with OK"
```
Set `OLLAMA_MODEL` in the backend `.env` to whatever you pulled.

### 0.6 Start the tools
- System A: `cd labellens && claude` → paste **Part 1 · Phase 1** from `prompts/PART1_PROMPTS.md`.
- System B: Claude Code in `labellens-part2` → **Part 2 · Phase 1**; Codex in `labellens-part3` → **Part 3 · Phase 1**.
- Let the tools run commands without asking every time (Claude Code: choose "always allow" for npm/git/python/pytest; Codex: use its auto/full-auto approval mode for the worktree).

---

## Day rhythm

1. Paste a phase prompt. While the tool works, humans do the human tasks for that phase (master spec §12).
2. When the tool prints its **PHASE REPORT**, a human follows "How to verify" (2 minutes). If something is broken, tell the tool exactly what you saw. Only then paste the next phase.
3. Tools commit and push to their own branch themselves. Check `git log --oneline -5` occasionally.

---

## Contract change protocol (rare — avoid if possible)
1. A tool writes the request in `<its folder>/NOTES_FOR_OTHERS.md`; a human decides.
2. On System B's `labellens/` (main): edit **both** `shared/contract.py` and `shared/contract.ts`, only **add optional fields**, bump `CONTRACT_VERSION` patch (1.0.0 → 1.0.1), regenerate fixtures (`python -m shared.fixtures.build_fixtures`), commit `[contract] ...`, push.
3. Every branch pulls main (see "Syncing" below) and tells its tool: "main changed shared/ — re-read the contract and adapt".

## Syncing a branch with main
```bash
git fetch origin
git merge origin/main          # inside the worktree / on System A's branch; resolve only in files you own
git push origin HEAD
```
Part 1 then runs `npm run sync-shared` to refresh `frontend/src/shared/`.

---

## Merge 1 (≈55 % of time) and Merge 2 (≈80 %)
Order: **engine → backend → frontend**.
```bash
# each part, from its own folder, after its checks pass:
gh pr create --base main --head part-3-engine   --title "[P3] engine phase 1-2" --fill
gh pr create --base main --head part-2-backend  --title "[P2] backend phase 1-2" --fill
gh pr create --base main --head part-1-frontend --title "[P1] frontend phase 1-2" --fill
# a human reviews the diff stats (each PR should only touch its own folder) and merges, in order:
gh pr merge <n> --merge
```
Then on System B, integration test in `labellens/` (main):
```bash
git pull
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate && pip install -r backend/requirements.txt -r engine/requirements.txt
# .env: ENGINE_MODE=real, VITE_USE_MOCKS=false
python -m pytest engine/tests backend/tests
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000        # terminal 1
cd frontend && npm install && npm run dev                       # terminal 2 (Node needed on the Mac too)
cloudflared tunnel --url http://localhost:5173                  # terminal 3: HTTPS link for the phone camera
```
Smoke test: scan 3 real packets; confirm all four states appear across them; tap evidence → highlight lands on the right words; switch language; ask one question. Then every branch syncs with main and continues.

After Merge 2, keep working on branches for fixes only; merge small PRs in the same order.

---

## Demo day checklist
- [ ] Backend + frontend + Ollama running on the Mac; `/api/health` shows engine `real`.
- [ ] `python backend/scripts/warm_cache.py` run on the demo packets (instant, quota-free scans).
- [ ] Phone opened via the cloudflared HTTPS link, camera permission granted, a test scan done.
- [ ] Public deployment (Vercel + HF Spaces) link works as backup; backup video ready offline.
- [ ] Repo public; README complete; `.env` not in history.
