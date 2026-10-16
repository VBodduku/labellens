# LabelLens

Point your phone at a packaged-food label. LabelLens reads it, checks it against every family member's allergies, diets and health limits, and shows **the exact words on the packet** behind every flag. When it can't read something, it says so instead of guessing.

> This README is the team kickoff index. Part 1 replaces it with the public project README in its final phase.

## What's in this kit

| Path | What it is | Who uses it |
|---|---|---|
| `docs/00_MASTER_SPEC.md` | The whole product: problem framing, principles, scope, architecture, API, verdict rules, timeline | Everyone (AI tools read it first) |
| `docs/PART1_FRONTEND_SPEC.md` | React PWA: capture, evidence viewer, family verdicts, i18n, voice | System A · Claude Code |
| `docs/PART2_BACKEND_SPEC.md` | FastAPI: OCR + LLM grounding, self-verification, agent, fallbacks | System B · Claude Code |
| `docs/PART3_ENGINE_SPEC.md` | Deterministic verdict engine, knowledge base, evaluation harness | System B · Codex |
| `docs/SETUP_AND_GIT.md` | Phase 0 setup, branches, worktrees, merges, demo checklist | Humans |
| `prompts/PART{1,2,3}_PROMPTS.md` | Paste-ready prompts for each phase | Humans → AI tools |
| `CLAUDE.md` / `AGENTS.md` | Rules the AI tools follow automatically | Claude Code / Codex |
| `shared/` | Frozen contract (Python + TypeScript), engine interface + stub, message templates, fixtures | Everyone |

## Start here
1. Humans: read `docs/00_MASTER_SPEC.md` §1–4 and edit §1–2 (problem framing, persona) in your own words if you want.
2. Follow `docs/SETUP_AND_GIT.md` Phase 0.
3. Paste Phase 1 from each prompts file into its tool.

## The fixture
`shared/fixtures/sample_label.svg` is a realistic label; `scan_result.json` is the full result for it with three family members (Aarav: peanut + tree-nut allergy; Thatha: diabetic + low sodium; Lakshmi: Jain + sesame allergy), covering all four verdict states. Regenerate with `python -m shared.fixtures.build_fixtures` from the repo root (needs `pydantic`).
