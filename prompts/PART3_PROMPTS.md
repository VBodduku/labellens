# Part 3 — Verdict engine + knowledge base + evaluation · phase prompts (System B, Codex, worktree `labellens-part3`, branch `part-3-engine`)

Paste one phase at a time into Codex. Wait for the PHASE REPORT, verify it yourself (2 minutes), then paste the next one.

---

## Phase 1 · KB foundations, matcher, core rules (0–25 %)

```
You are building Part 3 (the verdict engine, knowledge base and evaluation harness) of LabelLens. First read AGENTS.md, then docs/00_MASTER_SPEC.md completely — section 9 "Verdict semantics" is your specification — then docs/PART3_ENGINE_SPEC.md completely, then shared/contract.py, shared/engine_interface.py, shared/messages.en.json, shared/fixtures/catalog.json and shared/fixtures/scan_result.json. Confirm you are on branch part-3-engine. You may only write inside engine/. Run Python from the repo root (python -m pytest engine/tests).

Goal: a working, importable engine package with the public API, a first knowledge base, a robust matcher and the core verdict rules, all tested.

Do:
1. engine/ layout from spec §3; engine/requirements.txt; engine/__init__.py exporting exactly the five functions from shared/engine_interface.py (all must return valid contract objects from day one, even if some logic is basic).
2. kb_loader.py with Pydantic models for every KB file and validation at import (categories must be in shared.contract.CATEGORIES; catalog must contain every key in shared/fixtures/catalog.json).
3. kb/catalog.json (start from shared/fixtures/catalog.json), kb/names.json, kb/nutrients.json, kb/statement_items.json, kb/qualifiers.json, and kb/terms.json with ≥ 120 well-established entries covering spec §4 priorities (all allergens with Indian names, dairy and sugar hidden names, the INS codes listed, Jain items, palm oil). Follow the accuracy rule in spec §4: contested → possible_categories + notes; never invent INS numbers.
4. normalize.py and matcher.py per spec §5 (INS/E code extraction incl. multiple codes and (i)/(ii) suffixes, qualifiers, bracketed sub-lists, whole-word alias matching with compound-name protection, fuzzy fallback, unresolved terms). ≥ 40 matcher tests including the tricky cases in spec §10.
5. rules.py for the ingredient, allergen-statement and "no signal" (completeness) rows of master spec §9, severity handling for may-contain, worst-state precedence, evidence/matches ordering, confidence; messages.py rendering English explanations with the param conventions in spec §6. Table-driven tests for these rows.
6. DECISIONS.md and NOTES_FOR_OTHERS.md in engine/.

Done when: python -m pytest engine/tests passes; `python -c "import engine; print(len(engine.restriction_catalog()))"` works from the repo root; committed in small steps and pushed (git push origin HEAD). Finish with the PHASE 1 REPORT from AGENTS.md, including the KB entry count and any facts you were unsure about.
```

---

## Phase 2 · Full rules, nutrition consistency, explain, evaluation harness (25–55 %)

```
Phase 2 for Part 3. Re-read master spec §9 (all rows and notes) and engine spec §6–§9.

Goal: the complete rules engine, the nutrition cross-check that catches misreads, and the evaluation harness ready for real packets.

Do:
1. rules.py: remaining §9 rows — veg mark (both directions, including the "internally inconsistent label" note), thresholds at the requested basis with per-serving ↔ per-100 conversion, suspect-value handling, missing table/row, diabetes_sugar combining threshold + sugar alias, LLM interpretations (cap at possible, confidence × 0.8), unknown restriction keys, UnknownItem generation (truncated, unreadable regions, no allergen statement, unclear veg mark), overall per profile.
2. nutrition.py per spec §7: per_100 / per_pack, kJ→kcal, salt→sodium, the 4/4/9 energy check with the 15 % rule, single-field suspect detection (×10, ÷10, digit swaps, missing decimal), sanity checks, insufficient_data, notes. Tests with real-looking label numbers including deliberately misread ones.
3. explain.py per spec §8 with tests.
4. test_rules_table.py complete: one parametrised case per §9 row plus precedence cases. test_fixture_scenario.py: evaluate(shared fixture extraction, shared/fixtures/profiles.json) must reproduce every restriction's state, unknown_kind and reason_code in the fixture — this must pass.
5. Grow kb/terms.json to ≥ 200 entries.
6. eval/: dataset/README.md (instructions for the humans: how to photograph each packet — one clean shot per panel, one deliberately imperfect shot; ≤ 2000 px; folder naming), dataset/_template/truth.json, eval_profiles.json (~8 standard profiles), metrics.py and run_eval.py per spec §9 working against saved responses (create 2 synthetic packets from the fixture to test the harness end to end); writes reports/report.json, report.md, metrics.json.

Done when: all tests pass (report the count), the fixture scenario test passes, run_eval.py produces the three report files on the synthetic packets, committed and pushed. PHASE 2 REPORT — include the exact folder/format the humans must use for real packets.
```

---

## ⏸ Merge 1 (≈55 %) — humans
Follow docs/SETUP_AND_GIT.md "Merge 1" — the engine merges first. Then in `labellens-part3`:
`git fetch origin && git merge origin/main`. Make sure the humans have put real packet folders + truth.json files into `engine/eval/dataset/` (or a path they give you) and that the integrated backend is running on the Mac (http://localhost:8000).

---

## Phase 3 · Real-packet evaluation and improvement loop (55–80 %)

```
Phase 3 for Part 3. main has been merged into this branch. The integrated backend runs at http://localhost:8000 with ENGINE_MODE=real (if not, ask the humans to start it). Real packets with truth.json are in engine/eval/dataset/.

Goal: measured, honest accuracy on real packets, and the engine improved where it fails.

Do:
1. Run run_eval.py --backend http://localhost:8000 on all real packets; save responses to eval/responses/ so later runs can be offline.
2. Analyse every error: classify each as extraction (backend/LLM), KB gap, matcher bug, or rule bug. Fix KB/matcher/rule problems in engine/ with a regression test for each. Write extraction problems (with packet id and what went wrong) into engine/NOTES_FOR_OTHERS.md for Part 2.
3. Dangerous misses (expected conflict → predicted not_listed) are the top priority: there must be zero caused by the engine; explain any that come from extraction.
4. Grow kb/terms.json to ≥ 250 entries, add Hindi/Telugu names commonly printed on Indian labels, and list every contested/medium-confidence entry in engine/KB_REVIEW.md for a human to check.
5. Harden the matcher against the OCR typos and label phrasings seen in the real data.
6. Re-run the eval (offline from saved responses and once live) and compare before/after in report.md.

Done when: tests pass (count them), eval report shows before/after numbers, KB_REVIEW.md exists, committed and pushed. PHASE 3 REPORT with the headline metrics.
```

---

## Phase 4 · Final metrics, documentation, edge cases (80–100 %)

```
Phase 4 for Part 3 — feature freeze. No new rules unless they fix a dangerous miss.

Do:
1. Final live eval run; produce eval/reports/report.md (readable tables: extraction accuracy, verdict confusion matrix, dangerous-miss rate, evidence verified rate, unknown rate, latency) and eval/reports/metrics.json in the small format the frontend About page reads (agree on it via NOTES_FOR_OTHERS.md; keep keys simple: packets, ingredient_recall, ingredient_precision, nutrient_accuracy, verdict_accuracy, dangerous_miss_rate, evidence_verified_rate, unknown_rate, avg_latency_s, generated_at).
2. engine/README.md: how the four states are decided (with the §9 table in plain words), how matching works, how to add KB entries, how to run tests and eval, and honest limitations.
3. Edge-case tests: empty extraction, no profiles, profile with no restrictions, ingredients with only sub-ingredients, duplicated ingredients from multiple panels, absurd nutrient values, unknown restriction keys. evaluate() must never raise on valid contract input.
4. Performance check: evaluate() < 50 ms on the largest real label (report the timing).

Done when: tests pass, reports regenerated, committed and pushed. PHASE 4 REPORT with the final headline metrics to put in the pitch.
```

---

## Stretch (only if humans say so after Merge 2)

```
Stretch for Part 3: deterministic claim rules to support Part 2's claim check. Add engine/claims.py with a function check_claim(claim_text, extraction, nutrition_analysis) returning supported / contradicted / cannot_verify plus evidence, for a small fixed set of claim types (no added sugar, sugar free, high protein, low fat, no palm oil, vegetarian/vegan). Use conservative definitions and document their sources in engine/README.md; whenever a definition is uncertain, return cannot_verify. Do not change the public API in shared/engine_interface.py — expose it as an extra function and describe it in NOTES_FOR_OTHERS.md. Tests required. PHASE REPORT when done.
```
