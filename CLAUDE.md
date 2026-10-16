# LabelLens — instructions for AI coding agents

(This file is read by Claude Code. `AGENTS.md` has the same rules for Codex. Keep them identical in substance.)

LabelLens is a camera-first web app that reads a packaged-food label, structures it, and checks it against every family member's dietary profile — showing the exact words on the photo behind every flag and being honest about what it could not read.

## 1. Before you write any code
1. This is **one project** on `main` (the three parts are merged). Any folder may be changed when the task needs it.
2. Read `README.md`, then `docs/00_MASTER_SPEC.md` and the spec for the area you touch (`docs/PART1_FRONTEND_SPEC.md`, `docs/PART2_BACKEND_SPEC.md`, `docs/PART3_ENGINE_SPEC.md`), then `shared/`.
3. The specs and `shared/` are the source of truth for behaviour.

## 2. Structure
- `frontend/` React PWA · `backend/` FastAPI + AI pipeline · `engine/` deterministic verdict engine + KB + eval · `shared/` contract, engine interface, fixtures.
- `shared/contract.py` and `shared/contract.ts` must stay identical in shape. Change them together, only by adding optional fields, bump `CONTRACT_VERSION`, regenerate fixtures (`python -m shared.fixtures.build_fixtures`) and run `npm run sync-shared` in `frontend/`. Never edit `frontend/src/shared/` by hand.
- Record non-obvious choices in the `DECISIONS.md` of the folder you changed (one line each).

## 3. Product principles you must never break
- Four states only: conflict, possible ("Check this"), not_listed, unknown (not_detected / undeterminable). Never output or display "safe", "healthy" or "guaranteed".
- "Not listed" only when the relevant section was read completely. Otherwise unknown.
- Every flag carries evidence (exact label text + location), or explicitly says it couldn't be located.
- Verdicts come only from the deterministic engine. LLM interpretations can raise a result to "possible", never to "conflict".
- Always degrade gracefully (Gemini → Ollama → OCR-only; camera → upload; voice → typing).

## 4. Engineering standards
- TypeScript strict / typed Python everywhere. Small, single-purpose modules. No dead code, no commented-out code, no placeholder `TODO`s in core paths.
- Every user-facing flow has loading, empty and error states. Every network call has a timeout.
- Write tests as you go (Vitest for frontend utilities, pytest for backend and engine). Run them before reporting.
- Free and open-source only. No paid APIs, SDKs, fonts or services. No API keys in code or in git — read them from `.env` (copy `.env.example`).
- Cross-platform (Windows + macOS): LF line endings, file names and import paths in exact case, npm scripts without Unix-only commands, Python always run from the repo root (`python -m ...`) with Python 3.12.

## 5. Checks before saying you're done
```
python -m pytest engine/tests backend/tests
cd frontend && npm run build && npm run lint && npm run test
```

## 6. Git
- Small commits with a clear message (e.g. `scan: retry blurred nutrition rows`). Push when the human asks.
- Never commit `.env`, `node_modules`, `.venv`, caches, or large binaries.
- Never force-push or rewrite history.
