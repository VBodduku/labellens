# LabelLens — Evaluation, limitations and evidence traceability

Status as of 2026-10-17. This page reports what has been tested and measured so far, what has not, and how evidence traceability was improved. **Real-packet accuracy is pending:** no photographed packets have been scored yet, so every real-world number below is marked _pending_.

---

## 1. Summary

| Question | Answer today |
|---|---|
| Does the software behave as specified? | Yes, within the tested cases: 889 Python tests (887 pass, 2 live-Gemini tests skipped offline) and 128 frontend tests, all passing. |
| How accurate is it on real packets? | _Pending_ — 0 real packets scored. |
| Has it ever missed a conflict (expected conflict, predicted not listed)? | 0 dangerous misses in the synthetic check (0 / 9 expected conflicts). _Pending_ on real packets. |
| How fast is a scan? | _Pending_ as a measured figure. One informal free-tier session on 2026-10-16 saw fresh scans of ~40 s (see §5). Cache hits take 0.02–0.06 s. |

---

## 2. Test coverage

Run from the repo root:

```bash
python -m pytest engine/tests backend/tests
cd frontend && npm run test
```

### 2.1 By area

| Area | Tests | What they pin down |
|---|---:|---|
| Verdict rules (`engine/tests/test_rules_table.py`) | 113 | One case per row of the master spec §9 table, plus precedence (conflict beats unknown; preference + may contain; green mark + egg → conflict with an inconsistency note; truncated list → not detected; missing section → can't determine). |
| Matching (`test_matcher.py`, `test_normalize.py`) | 132 | Hidden names and INS codes; false-hit guards (coconut ≠ tree nut, cocoa butter ≠ dairy); qualifiers ("INS 322 [Soy]"); negated qualifiers; OCR typos ("pea nuts", "whey pow der"). |
| Knowledge base (`test_kb_valid.py`, `test_kb_phase2.py`, `test_kb_phase3.py`, `test_catalog.py`) | 141 | Every category in the fixed vocabulary, no duplicate aliases or INS codes, Hindi/Telugu names, every catalog key present. |
| Dangerous regressions (`test_dangerous_regressions.py`) | 14 | An explicit allergen can never be lost by list splitting, normalisation or fuzzy repair. |
| Edge cases (`test_edge_cases.py`) | 61 | Empty inputs, no profiles, nested-only ingredients, unknown keys, extreme and non-finite numbers. |
| Nutrition (`test_nutrition.py`, `test_consistency.py`) | 66 | Per-100 / per-pack conversion, kJ and salt conversion, the energy cross-check and which value is suspect. |
| Contradictions and confirmations (`test_contradictions.py`) | 15 | Veg mark vs ingredient, "free from" vs ingredient, claim vs label, AI vs print, photo vs photo; user confirmations; unrecognised ingredients block "not listed". |
| Fixture scenario, explain, eval harness | 87 | The demo label reproduces every fixture verdict; KB explanations; the scorer, reports and before/after comparison. |
| Backend pipeline (`backend/tests`) | 260 | Alignment statuses (verified / approximate / unverified), OCR word boxes, focus crop and mapping back, panel merge, self-check triggers and budget, fallback chain, interpretation vocabulary filter, summary banned-word filter, agent guard, profile parsing, every endpoint, log hygiene. |
| Frontend (`frontend/src/**/*.test.ts*`) | 128 | Message rendering in en/hi/te, every message key translated, banned words absent from copy, evidence box maths, corrections and confirmations, API client and mocks, stores. |

### 2.2 Against the four scenarios to test

| Scenario | Where it is covered |
|---|---|
| Matching evidence | Alignment tests (cited tokens and window search → `verified`, one Evidence per printed line); fixture scenario ("Peanuts (22%)" → conflict for the peanut profile, with its words on the photo). |
| Contradictory interpretations | `test_contradictions.py` (all five kinds); alignment tests for AI vs printed numbers (a disagreement leaves the value unused and recorded); merge tests for photos that disagree; a green mark never overrides a listed egg. |
| Ambiguous ingredients | Rules table rows for "varies" origin (INS 471, natural flavours, lecithin with no source), qualifiers that resolve them, the veg mark resolving only slaughter-derived ambiguity; LLM interpretations capped at "Check this"; confirmations settling them. |
| Different dietary preferences | Eight evaluation profiles (peanut, milk, gluten, vegetarian, vegan, Jain, diabetic sugar limit, low sodium); strict vs preference severity (may contain → "Check this" vs "Not listed" with a note); threshold-only restrictions. |

What tests do **not** prove: how well OCR and the model read real, curved, glossy packets. That needs the real-packet run in §4.

---

## 3. Synthetic pipeline check

Source: `engine/eval/reports/report.md` (generated 2026-10-16). Two saved responses built from the demo label, scored against all eight evaluation profiles:

- `synthetic_clean` — the demo label as extracted.
- `synthetic_imperfect` — the same label deliberately damaged: truncated list, unreadable peanuts, no readable allergen statement, unclear veg mark, and carbohydrate corrupted from 58 g to 5.8 g.

**These are software checks, not accuracy.** They show the scorer works and the engine responds conservatively to bad input.

| Measure | Synthetic result |
|---|---:|
| Ingredient precision | 100.00% |
| Ingredient recall | 95.45% |
| Nutrient values | 93.75% |
| Allergen statements (exact sets) | 100.00% |
| Veg mark | 100.00% |
| Verdict accuracy (profile overall) | 93.75% |
| Dangerous-miss rate | 0.00% (0 / 9) |
| Evidence verified rate | 95.71% |
| Unknown rate | 18.75% |

Confusion matrix (rows expected, columns predicted):

| | conflict | possible | unknown | not_listed |
|---|---:|---:|---:|---:|
| conflict | 8 | 1 | 0 | 0 |
| possible | 0 | 3 | 0 | 0 |
| unknown | 0 | 0 | 3 | 0 |
| not_listed | 0 | 0 | 0 | 1 |

The one error is intended. The corrupted carbohydrate (5.8 g) is less than the sugar reading (38 g), so both values become suspect. The engine therefore withholds the sugar-limit conflict and reports "Check this" from the sugar aliases, instead of trusting a number it knows is wrong. The missing peanut is reported as unknown, not "not listed".

Reproduce:

```bash
python -m engine.eval.build_synthetic
python -m engine.eval.run_eval --dataset engine/eval/synthetic/dataset --responses engine/eval/synthetic/responses
```

---

## 4. Real-packet results — pending

`engine/eval/reports/metrics.json` has `"status": "pending"`, 0 packets and null rates, and the About page shows "coming soon" until real packets are scored.

| Measure | Real packets |
|---|---|
| Packets scored | _pending_ (target 10–15) |
| Ingredient precision / recall | _pending_ |
| Nutrient value accuracy | _pending_ |
| Allergen statement accuracy | _pending_ |
| Veg mark accuracy | _pending_ |
| Verdict accuracy and confusion matrix | _pending_ |
| Dangerous-miss rate | _pending_ |
| Evidence verified rate | _pending_ |
| Unknown rate | _pending_ |
| Average request latency | _pending_ |

To fill this in: photograph packets and write a `truth.json` for each (`engine/eval/dataset/README.md`), capture responses from the running backend, score them, copy `metrics.json` to `frontend/public/metrics.json`, and replace this table.

---

## 5. Limitations

**Measurement**
- No real-packet accuracy yet (§4). The synthetic numbers must not be quoted as accuracy.
- The p50 ≤ 8 s scan target was not met or fairly measured. On 2026-10-16 the free Gemini tier queued even trivial calls (~9 s), structuring took 13–27 s and fresh scans were ~40 s. Full Flash models returned 503 for minutes, and `gemma3:4b` on a MacBook Air needed > 90 s per label, so scans fell back to OCR-only. Pre-scanned packets (cache hits) answer in 0.02–0.06 s.
- Camera quality thresholds (blur 100, glare 3 %) are provisional until calibrated on the demo phone.

**Reading the label**
- RapidOCR reads Latin script well. Hindi and Telugu print is read by the model only, so its evidence is `approximate` (the model's own box), not `verified` against OCR words.
- OCR-only mode (every model down) marks all sections incomplete, so it can never say "not listed". It finds far fewer items and always reports the veg mark as unclear.
- A list cut off at the photo edge cannot be fixed by re-reading. The user is asked to retake.

**Knowledge base**
- 263 entries, of which 40 await human review (`engine/KB_REVIEW.md`): contested additive origins, dried ginger/turmeric for Jain diets, spice blends and flavourings.
- Taxonomy simplifications kept from the spec: lactose maps to milk, lactitol to milk origin, and maltodextrin and date paste to sugar aliases. These are broad screens, not clinical or regulatory claims.
- Hindi/Telugu aliases and all hi/te UI and agent text still need native-speaker review (`docs/TRANSLATION_REVIEW.md`).
- No regional names for celery, lupin or molluscs. English names only.

**What the product does not do**
- It does not certify products and never says "safe", "healthy" or "guaranteed". Banned words are filtered from summaries and agent answers in all three languages, and a frontend test checks the UI copy.
- It does not infer hidden ingredients. Only printed text is matched. An unknown ingredient on a complete list is "Unknown" ("we don't know what X is made of"), not "not listed". An AI interpretation can raise a result to "Check this", never to "Conflict".
- It gives no medical advice. Dosage, medicine and treatment questions (en/hi/te) are refused and redirected to a doctor, and the footer and About page say so.
- A "may contain" warning reflects the label only. It cannot measure cross-contact.

---

## 6. Evidence traceability and reliability improvements

Each item is a change made while building. The reasons are recorded in each folder's `DECISIONS.md`.

**Locating words on the photo**
- Word boxes come from RapidOCR's per-character boxes instead of splitting a line evenly. Recall of the demo label's words went from 80 % to 96 %.
- Window search only accepts matches of similar length to the item, so "Sugar" can no longer be pinned to "Invert Sugar Syrup".
- Verified evidence is split into one box per printed line, so a highlight never covers unrelated text between lines.
- Photos are cropped to the text and turned upright before reading. Every box is then mapped back to the full photo, so highlights land on the original image. On a sideways photo, Gemini went from reading 0 ingredients to reading all of them.
- Evidence that can't be located is kept as `unverified` with its text and a "Couldn't locate on photo" chip. No box is ever invented.

**Numbers**
- A nutrient value must agree between the model and the printed OCR text. When they disagree, the value is not used for verdicts, and the disagreement is recorded and shown as an "AI vs print" contradiction. A lost decimal point ("8.8" read as "88") counts as agreement.
- A number that appears nowhere on the photo is dropped (`value_not_on_photo`). In testing, `gemma3:4b` had invented "175 mg" for a smudged sodium value.
- The energy cross-check marks the likely misread field as suspect. A suspect value is never used for a threshold check, and the engine never rewrites it.

**Structure**
- A sub-ingredient is accepted only if its text appears inside its parent's printed text (the local model had nested every item under the first).
- When two photos of the same packet disagree on a value, it is recorded with both values and shown as a "panels" contradiction. Two rows on one photo are not counted.

**Honest answers**
- Contradictions (contract 1.0.1): veg mark, "free from", claims, AI vs print and photo vs photo are shown with both sides' evidence and the verdicts they affect. Each offers "fix a misread" (recheck) or "checked on the pack".
- Confirmations (contract 1.0.1): an ambiguous, AI-interpreted or unknown ingredient can be settled from the pack. The result then says "You checked the pack", never presenting the user's answer as the engine's finding. A confirmation cannot override a definite database fact.
- A readable ingredient that neither the database nor an interpretation explains blocks "not listed". When interpreting, whole unknown ingredients are sent to the model ahead of leftover words, so the terms that matter most are covered.
- The "couldn't read" list starts with the photo problems that caused the gaps, names each row as printed, offers a retake for the exact region and shows each problem once.
- The result screen separates confirmed findings, uncertain ones, missing information and open contradictions for each person.

---

## 7. Next steps

1. Score 10–15 real packets and replace §4 (including a measured latency).
2. Human review of the 40 knowledge-base entries and the hi/te translations.
3. Calibrate camera quality thresholds on the demo phone.
4. Re-run the evaluation after the contract 1.0.1 work is committed, and compare before and after on the same packets.
