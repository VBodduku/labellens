# Real-packet evaluation collection

Collect 10–15 distinct packaged foods, including allergens, ambiguous additives,
a Jain conflict, sugar and sodium limits, and products with no tracked ingredients.
Use the same eight profiles in `engine/eval/eval_profiles.json` for every scan.
Every product should have a clean case and a deliberately imperfect case. Report
case counts separately from the number of distinct physical products.

## Photos and exact folders

From the repository root:

```
engine/eval/dataset/
  001_brand_product_clean/
    img_0.jpg
    img_1.jpg                 # optional second panel
    img_2.jpg                 # optional third panel
    truth.json
  001_brand_product_imperfect/
    img_0.jpg                 # one deliberately imperfect shot
    truth.json
engine/eval/responses/
  001_brand_product_clean.json
  001_brand_product_imperfect.json
```

Use lowercase ASCII letters, numbers and underscores for case IDs. The saved
response filename must exactly match its dataset folder ID. Use up to three panels
in upload order (`img_0`, `img_1`, `img_2`). Take one sharp, evenly lit shot per panel:
keep the camera square to the label, avoid reflections, and include the complete
ingredient list, allergen warnings, nutrition headers/values and veg mark across
those panels. Do not combine different products in one case.

Also take one deliberately imperfect shot of the same product: choose blur, glare,
a fold, or a cut-off list. Keep it separate from the clean case. Annotate the
completeness and expected unknowns for that case's photos; do not treat absent
image text as absent ingredients.

Resize each image to **at most 2000 pixels on the longest edge**, use JPEG, and
keep each file **at most 400 KB**. Check that clean-case small text remains readable
after resizing. Do not upscale a poor photo and call it clean. Images and local
responses are ignored by Git; commit photos only after the team's agreement.

## Human truth

Copy `_template/truth.json` into each case folder and replace its contents. The
runner excludes underscore-prefixed template folders. A second person should check
the truth against the packet and the exact photos. Do not copy scanner output into
truth, and do not generate expected states by calling the engine being evaluated.

The format is JSON:

```json
{
  "source": "real",
  "product": "Exact product name",
  "ingredients": ["Wheat flour", "Salt"],
  "ingredients_complete_in_photos": true,
  "allergen_statements": {"contains": ["Wheat"], "may_contain": []},
  "veg_mark": "veg",
  "nutrition_per_100_unit": "g",
  "nutrition_per_100": {"energy_kcal": 350, "total_sugars_g": 3, "sodium_mg": 10},
  "nutrition_rounding": {"energy_kcal": 0.5, "total_sugars_g": 0.5, "sodium_mg": 0.5},
  "expected": [
    {"eval_profile": "peanut", "state": "not_listed"},
    {"eval_profile": "milk", "state": "not_listed"},
    {"eval_profile": "gluten", "state": "conflict"},
    {"eval_profile": "vegetarian", "state": "not_listed"},
    {"eval_profile": "vegan", "state": "not_listed"},
    {"eval_profile": "jain", "state": "not_listed"},
    {"eval_profile": "diabetes_sugar", "state": "not_listed"},
    {"eval_profile": "low_sodium", "state": "not_listed"}
  ]
}
```

That example illustrates a simple pasta label; it is not collected evidence. Replace
every field with the actual packet's truth. The template defaults expected verdicts
to unknown until a human reviews them.

- Transcribe top-level ingredient items verbatim, including bracketed component lists.
  A clean physical reference can establish the ingredient truth for recall scoring;
  the completeness flag and expected states must describe the actual case photos.
- Transcribe allergen statement items by type: contains, may_contain, facility, or
  free_from. Use only statements visible in this case. Empty arrays are allowed.
- Use veg/non_veg/not_found/unclear. A green mark does not remove explicit egg,
  dairy, honey, insects, onion, garlic or root-vegetable signals.
- Enter readable per-100 nutrient values in canonical keys/units (g, mg, kcal).
  Set nutrition_per_100_unit to ml for per-100 ml tables; do not assume density.
  Omit unreadable numeric values rather than guessing them. For salt-only rows,
  sodium mg = salt g x400; energy kcal = kJ /4.184.
- nutrition_rounding is an optional absolute tolerance in those same units: 12.3 g
  has a half-last-digit tolerance of 0.05 g; 160 mg has 0.5 mg. Convert the tolerance
  too if converting salt or kJ. The scorer accepts max(2% of truth, this tolerance).
  Without an annotation, only the 2% rule applies. Do not add arbitrary tolerances.
- Expected states are conflict, possible, unknown or not_listed. Use master-spec §9
  and the fixed profile thresholds. Incomplete sections cannot justify absence.
  A label-origin ambiguity or strict trace warning is possible. Do not infer a
  missing number. Green marks resolve only the specified slaughter-derived ambiguity.

## Saved responses and running

Send each case's images to the backend with all eight profiles from
`engine/eval/eval_profiles.json`, and save the complete returned **ScanResult JSON**
as `engine/eval/responses/<case_id>.json`. Include extraction, nutrition_analysis,
reports and metadata. A typical scanner response made with different profile IDs
is not a valid substitute: missing IDs are listed and always fail verdict accuracy
(the confusion matrix places them under unknown). A missing
response file aborts the run.

From the repository root, in the project's Python environment:

```
python -m engine.eval.run_eval --backend http://localhost:8000 --reports engine/eval/reports/before
```

This requires a running backend with `ENGINE_MODE=real`, uploads every case with
the fixed profiles, saves full responses to `engine/eval/responses/<case_id>.json`,
and writes `report.json`, `report.md`, and `metrics.json` in the chosen directory.
Health, timeout, malformed responses and per-case failures abort scoring. A capture
manifest records providers, cache hits and request durations. Fixture extractions
cannot measure real-packet accuracy. JPEG/PNG panels must be contiguous and at most
400 KB each; image dimensions are validated by the backend.

Before changing engine code, keep that baseline directory and raw responses. After
fixes, replay **the same extraction** to isolate engine changes:

```
python -m engine.eval.run_eval --reevaluate --baseline engine/eval/reports/before/report.json --reports engine/eval/reports/after_offline
```

Replay leaves original responses unchanged and saves derived responses in
`engine/eval/responses/reevaluated/`. Original LLM interpretations, if still needed,
must be supplied in `<case_id>.interpretations.json`, a JSON object mapping unresolved
term text to the frozen `TermInterpretation` shape (`term`, `categories`, `origin`,
`confidence`, `rationale`). Missing original interpretation inputs block replay;
they are never reconstructed from verdicts.

Restart the backend so it loads the changed engine, then capture into a **different**
response directory to preserve the baseline:

```
python -m engine.eval.run_eval --backend http://localhost:8000 --responses engine/eval/responses/after_live --baseline engine/eval/reports/before/report.json --reports engine/eval/reports/after_live
```

Both after reports contain before/after values. Comparison requires identical
packet IDs, truth, photos and profiles. An engine fingerprint identifies local code;
it cannot prove which checkout a separate backend process has loaded. The ordinary
offline scorer (`--responses engine/eval/responses`, without `--reevaluate`) scores
saved reports as supplied and never calls a model or backend.

Review every error in `report.json.errors` against the photo and raw extraction.
Record reviewed causes in e.g. `engine/eval/classifications.json`:

```json
{
  "001_brand_product_clean:verdict:milk": {
    "category": "extraction",
    "explanation": "Photo shows milk powder; the extracted list omitted that item."
  }
}
```

Categories are `extraction`, `kb_gap`, `matcher_bug`, `rule_bug`. Engine-owned causes
also require `regression_test`, an exact test path/name. This example is hypothetical,
not an observed failure. Pass `--classifications engine/eval/classifications.json`
when scoring; recheck reviews against each run. Unreviewed dangerous misses leave
`engine_dangerous_misses` null, never a misleading zero. Copy actual packet-specific
extraction findings into `engine/NOTES_FOR_OTHERS.md` for Part 2.

The markdown report defines each rate and shows the four-by-four confusion matrix.
The dangerous-miss rate is expected conflict predicted not_listed divided by all
expected conflicts. Also inspect conflict-to-unknown and conflict-to-possible errors.
Undefined rates are null; latency uses positive saved extraction durations.

## Synthetic verification

Two fixture-derived cases are isolated under `engine/eval/synthetic/`. They never
mix with this real dataset. Reproduce them and their reports with:

```
python -m engine.eval.build_synthetic
python -m engine.eval.run_eval --dataset engine/eval/synthetic/dataset --responses engine/eval/synthetic/responses
```

The checked-in reports are explicitly synthetic and contain **zero real packets**.
They demonstrate the harness and one deliberate numeric error, not real accuracy.
Replace them with reviewed real-packet reports before using metrics in a pitch or
on the frontend. The runner rejects a mixed real/synthetic dataset.
