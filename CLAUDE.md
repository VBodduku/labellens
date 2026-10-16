# LabelLens — instructions for AI coding agents

(This file is read by Claude Code. `AGENTS.md` has the same rules for Codex. Keep them identical in substance.)

LabelLens is a camera-first web app that reads a packaged-food label, structures it, and checks it against every family member's dietary profile — showing the exact words on the photo behind every flag and being honest about what it could not read.

## 1. Before you write any code
1. Run `git branch --show-current`. Your branch decides your part:
   - `part-1-frontend` → **Part 1**, you own `frontend/` → read `docs/PART1_FRONTEND_SPEC.md`
   - `part-2-backend` → **Part 2**, you own `backend/` → read `docs/PART2_BACKEND_SPEC.md`
   - `part-3-engine` → **Part 3**, you own `engine/` → read `docs/PART3_ENGINE_SPEC.md`
   - `main` → integration only; change nothing unless the human explicitly asks.
2. Read `docs/00_MASTER_SPEC.md` completely, then your part spec, then everything in `shared/`.
3. The specs and `shared/` are the source of truth. Do not look for or rely on any other problem description.

## 2. Ownership (hard rules)
- Write **only** inside the folder your part owns. Reading anything is fine.
- Never edit `shared/`, `docs/`, `prompts/`, root config files, or another part's folder. If you need a change there, append it to `NOTES_FOR_OTHERS.md` inside your own folder, explain why, and tell the human in your report.
- `shared/contract.py` / `shared/contract.ts` are frozen. Build exactly to them. Never redefine contract types locally with different shapes (Part 1 uses the synced copy in `frontend/src/shared/`).

## 3. Product principles you must never break
- Four states only: conflict, possible ("Check this"), not_listed, unknown (not_detected / undeterminable). Never output or display "safe", "healthy" or "guaranteed".
- "Not listed" only when the relevant section was read completely. Otherwise unknown.
- Every flag carries evidence (exact label text + location), or explicitly says it couldn't be located.
- Verdicts come only from the deterministic engine. LLM interpretations can raise a result to "possible", never to "conflict".
- Always degrade gracefully (Gemini → Ollama → OCR-only; camera → upload; voice → typing).

## 4. Engineering standards
- TypeScript strict / typed Python everywhere. Small, single-purpose modules. No dead code, no commented-out code, no placeholder `TODO`s in core paths when you report a phase done.
- Every user-facing flow has loading, empty and error states. Every network call has a timeout.
- Write tests as you go (Vitest for frontend utilities, pytest for backend and engine). Run them before reporting.
- Free and open-source only. No paid APIs, SDKs, fonts or services. No API keys in code or in git — read them from `.env` (copy `.env.example`).
- Cross-platform (Windows + macOS): LF line endings, file names and import paths in exact case, npm scripts without Unix-only commands (use small Node scripts instead of `rm -rf`, `cp`, `export VAR=...`), Python always run from the repo root (`python -m ...`).

## 5. Git
- Commit after each working sub-feature with a message like `[P1] evidence viewer: focus + mask animation`. Push to your own branch at least every 30–45 minutes: `git push origin HEAD`.
- Never commit `.env`, `node_modules`, `.venv`, caches, or large binaries.
- Never force-push, never rewrite history, never merge into `main`, never switch branches. Humans do merges.

## 6. How to work through a phase prompt
1. Restate the phase goal in 2–3 lines and list the files you will create or change.
2. Implement in small verified steps; run the app/tests often.
3. If the spec is silent, choose the simplest option consistent with the principles and record it in `DECISIONS.md` in your folder (one line each).
4. Before saying you're done: run your part's checks (Part 1: `npm run build && npm run lint && npm run test` in `frontend/`; Part 2: `python -m pytest backend/tests`; Part 3: `python -m pytest engine/tests`), commit, push.
5. End with this report:
   ```
   PHASE <n> REPORT — Part <x>
   Done: <bullets>
   How to verify (human, 2 minutes): <exact commands / clicks>
   Not done / known issues: <bullets>
   Notes for other parts / contract requests: <bullets or "none">
   Next phase ready: yes/no
   ```
