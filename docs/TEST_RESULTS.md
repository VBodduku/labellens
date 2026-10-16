# Acceptance test results

Three acceptance tests: a clear label, a partly unreadable label, and conflicting or incomplete information. Each
was run against the real backend and engine with fresh AI readings (no cache), three times.

- **Date:** 2026-10-17. **Reader:** Gemini (`gemini-flash-lite-latest`; the configured `gemini-3.5-flash` was
  overloaded, so the fallback chain answered), RapidOCR, rules engine.
- **Photo:** the back label of a Bingo snack pack (`dataset _images/img_5.jpeg`, 1080 × 1276). The pack has
  **no veg mark**. Test 2 and Test 3 are the same photo, edited by the runner.
- **Profiles:** Asha (milk allergy, peanut allergy), Ravi (Jain, vegetarian), Dadi (diabetic: sugar ≤ 22.5 g per
  100 g; low sodium: ≤ 600 mg per 100 g). All strict.
- **Re-run:** `python -m backend.scripts.acceptance_tests "<photos dir>" --url http://localhost:8000`. It builds the
  three photos, scans them, checks every verdict against what the photo justifies, checks that every flag has
  evidence, and saves the evidence JSON.
- **Evidence:** [`docs/test_evidence/run1`](test_evidence/run1), [`run2`](test_evidence/run2),
  [`run3`](test_evidence/run3). The failing runs from before the last fix are in
  [`before_veg_mark_fix`](test_evidence/before_veg_mark_fix).

## Summary

| Test | What it checks | Expected | Actual (3 fresh runs) | Result |
|---|---|---|---|---|
| 1. Clear label | Extracted text is compared correctly with each preference; every flag has evidence | Milk **Conflict**, Jain **Conflict**, Vegetarian **Check this**, Sugar **Check this**, Sodium **Conflict** (701.1 mg > 600), Peanut Not listed or Unknown | Exactly as expected in 3/3 runs; Peanut was Not listed in 2 runs and Unknown in 1 (see "Misses") | **Pass** |
| 2. Ingredient list and sodium value blurred | Unreadable fields are marked uncertain; nothing absent is assumed | Peanut, Jain, Vegetarian **Unknown** (list unreadable); Sodium **Unknown**; Milk **Conflict** (the "Contains milk" line stays readable) | As expected in 3/3 runs; a "Retake this area" region is given for sodium | **Pass** |
| 3. Lower half of the nutrition table covered | Incomplete panel; AI reading vs printed text; uncertainty shown | Sodium **Unknown**, never "within limit"; other verdicts as in Test 1 | As expected in 3/3 runs; values the AI put on covered rows were marked unreadable and not used | **Pass** |

Before the last fix, Vegetarian came out **Not listed** in 3 of 9 runs (Test 1 and Test 3). That was a
**dangerous answer**: the AI invented a located green veg mark. See Fix 4.

## Test 1: clear label and stated preferences

**Steps:** scan the unedited photo with the three profiles.

**Expected:** the extracted text matches the label, and each verdict follows from it with evidence.
- Milk solids and cheese powder → milk Conflict.
- Onion and garlic powder → Jain Conflict.
- INS 635 and natural flavours (source not stated) → Vegetarian Check this.
- Sugar and maltodextrin, with 3.1 g sugars per 100 g → Check this.
- Sodium 701.1 mg per 100 g against a 600 mg limit → Conflict.

**Actual (run 1):**

| Restriction | State | Reason shown to the user | Evidence (text on the photo) |
|---|---|---|---|
| Milk allergy | Conflict | Lists MILK SOLIDS — this counts as milk. | "MILK SOLIDS", "CHEESE POWDER (O.5%)", located |
| Peanut allergy | Unknown | We don't know what YEAST EXTRACTANDACIDITY is made of, so peanut can't be ruled out. | "YEAST EXTRACTANDACIDITY" |
| Jain | Conflict | Lists ONION POWDER — this counts as onion. | "ONION POWDER", "GARLIC POWDER" |
| Vegetarian | Check this | NATURE IDENTICAL FLAVOURING SUBSTANCES can come from animal-derived sources | flavouring substances, "FLAVOUR ENHANCERS (508, 635)" |
| Diabetic: sugar | Check this | Sugars is a form of sugar. | "Sugars", "MALTODEXTRIN", "3.1" |
| Low sodium | Conflict | Sodium is 701.1 mg per 100 g, above your limit of 600.0 mg. | "701.1" |

- All 10 nutrition rows were read with the printed numbers.
- In this run the AI claimed a green veg mark the pack doesn't have. It was set to unclear, and "Veg mark unclear" appears under "Couldn't read".
- **Pass:** every Conflict and Check this flag has evidence from the photo.

## Test 2: partially unreadable label

**Steps:** the runner blurs the ingredient list and the sodium values (Gaussian blur), then scans.

**Expected:**
- Nothing is called "Not listed" from a list nobody could read.
- The blurred sodium value is Unknown, never "within limit".
- The app points to where a clearer photo is needed.

**Actual (all 3 runs):**
- The ingredient section was not found (it was unreadable). Peanut, Jain and Vegetarian are **Unknown**: "No ingredient list was found in these photos."
- Sodium is **Unknown**: "Sodium is not readable on this label." The value was stored as unreadable, not invented.
- "Couldn't read" lists **Retake this area: Sodium (mg)** with the region on the photo, which asks for a clearer image.
- Milk is **Conflict** from the readable "CONTAINS MILK" statement, with that statement as evidence.
- Sugar is Not listed (3.1 g is within the limit). The sugar row is readable.
- **Pass:** no undetected ingredient was treated as absent.

## Test 3: conflicting or incomplete information

**Steps:**
- The runner covers the lower half of the nutrition table (total fat to sodium) with the pack's purple, then scans.
- The AI-vs-printed-text case is also covered by a permanent automated test (below).

**Expected:**
- Covered rows are uncertain.
- No value is moved from one row to another.
- Ambiguous ingredients are Check this.
- Where the AI's reading and the printed text disagree, the printed text wins and the disagreement is shown.

**Actual (all 3 runs):**
- The AI listed Total Fat 3.1, Saturated Fat 2.1 and Sodium **24.1** for the covered rows. Those numbers belong to other rows.
- The row check marked all three **unreadable** ("May be misread"), and the engine did not use them.
- Sodium is **Unknown**, not "within limit". Before Fix 2, this case gave a wrong "within limit".
- The ingredient list was flagged as cut off at the photo edge. Peanut is Unknown: "Part of the ingredient list is cut off. No peanut found in the readable part."
- Vegetarian is Check this (ambiguous INS 635 / natural flavours), showing the original label text.
- **AI vs printed text:** `test_the_ai_misreading_a_printed_number_is_shown_and_not_used`.
  - The AI reads 33.0 where the label prints 38.0.
  - The result shows a contradiction with both texts, and the engine uses the printed 38.0.
- **Pass.**

## Requirement checklist

| # | Requirement | Where it is met |
|---|---|---|
| 1 | Clear label compared correctly with the preference | Test 1: all six verdicts match the label |
| 2 | Every flag has supporting evidence from the label | All tests; the runner fails a test if any Conflict or Check this has no evidence |
| 3 | Unreadable fields marked uncertain | Test 2 (ingredients, sodium), Test 3 (covered rows) |
| 4 | Asks for a clearer image or confirmation instead of assuming absence | "Retake this area" regions (Test 2, 3); "I checked the pack" confirmation; no Not listed from unreadable text |
| 5 | Ambiguous text, incomplete panel, AI vs printed text | Test 1/3 (INS 635, natural flavours), Test 3 (covered rows), contradiction test |
| 6 | Shows original source text, identifies uncertainty, asks for confirmation | Evidence chips quote the label text; Unknown states say why; contradictions show both readings |
| 7 | No invented label details, no safety guarantees | Invented values and the invented veg mark are rejected (Fixes 1–4); the four states never say "safe" (a test checks every UI string) |

## Issues found and fixed during testing

Each fix has a permanent automated test.

1. **A veg mark the AI could not locate was trusted.** In one run the AI claimed a green veg mark and Vegetarian went
   to Not listed. Now a green mark without a location counts as unclear.
   Test: `test_a_veg_mark_the_model_cannot_locate_never_loosens_a_verdict`.
2. **Numbers landed on the wrong rows.** With the table covered, a re-read put Total Fat's 24.1 under Sodium, so a
   sodium value nobody could see read as "within limit". Now a number counts only on its own row's line, and a row
   whose label is not on the photo is never used.
   Tests: `test_a_value_from_another_row_is_not_used_for_this_row`, `test_a_row_whose_label_is_not_on_the_photo_is_never_used`,
   `test_the_same_number_on_the_right_line_is_used_instead`.
3. **A sharp "CONTAINS MILK, SOY" was sometimes missed by the AI.** When the AI reports no allergen statement, the
   app now reads one from the OCR words.
   Test: `test_an_allergen_statement_the_ai_left_out_is_read_from_the_ocr_words`.
4. **The AI invented a located green veg mark (3 of 9 runs).** Fix 1 did not catch this because the AI also gave a
   box. Now the photo's pixels in and around the box must actually be green (`backend/app/pipeline/veg_mark.py`):
   - The real veg mark on another pack scored 0.10 (0.012 with a box three times too big).
   - This pack scored 0.000 everywhere.
   - Otherwise the mark counts as unclear. A brown non-veg mark is never downgraded.

   After the fix: 9 of 9 runs pass, and Vegetarian is Check this every time. Tests: `backend/tests/test_veg_mark.py`.

## False positives

- **Glare warning on a clean image.** In run 1 of Test 1, "Photo has glare" appeared although the photo is a clean
  digital image. The white barcode and QR areas count as blown-out highlights. The glare threshold is still uncalibrated
  (`backend/app/pipeline/quality.py`).
- No false Conflicts. Every Conflict matches printed text.

## Misses and weaker answers

- **Peanut was Unknown, not Not listed, on the clear label in run 1** (Not listed in runs 2 and 3). OCR glued "YEAST EXTRACT AND ACIDITY" into
  "YEAST EXTRACTANDACIDITY", which the knowledge base cannot resolve, so peanut can't be ruled out. That's honest but
  over-cautious.
- **One Test 1 run in the earlier round missed sodium,** giving Unknown instead of Conflict. It did not recur in
  the 9 runs after the fixes.
- **Sugar in Test 2 is Not listed** from the readable sugar row, although the blurred list may hide sugar aliases.
  The spec allows this (the threshold decides), but a stricter rule would be Check this.
- **Allergen statement text is sometimes garbled or duplicated** (e.g. "MAY CONTAIN WHEAT, ARL Y" for "BARLEY").
  The verdicts were still right, because "milk" and "soy" were read correctly.
- **The Unknown sodium verdict in Test 3 still lists the rejected "24.1" as evidence.** The value isn't used, but
  showing it may confuse a user.

## Improvements still worth making

- Split OCR-glued words before matching ingredients ("EXTRACTANDACIDITY" → "EXTRACT AND ACIDITY").
- Calibrate the glare threshold on real phone photos; exclude barcode and QR areas.
- Leave rejected values out of a verdict's evidence list.
- Repeat these tests on 10+ real packets (`engine/eval/`) for measured accuracy.
