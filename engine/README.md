# LabelLens engine

Pure deterministic Python, with the five functions specified in
`shared/engine_interface.py`. Run Python from the repository root. No network or
model calls occur when importing or evaluating the engine. The offline evaluation
runner uses saved JSON by default; its explicit `--backend` option captures HTTP
responses outside the public engine API.

Create a Python 3.11+ environment from the repository root:

```
python -m venv engine/.venv
```

Activate it with `source engine/.venv/bin/activate` on macOS/Linux, or
`engine\.venv\Scripts\activate` on Windows. Then run from the repository root:

```
python -m pip install -r engine/requirements.txt
python -m pytest engine/tests
python -c "import engine; print(len(engine.restriction_catalog()))"
```

On this machine the task environment is `engine/.venv` (macOS/Linux activation:
`source engine/.venv/bin/activate`; Windows: `engine\.venv\Scripts\activate`).
Environments, downloaded dependencies, caches, real photos and local scan responses
are ignored by Git. The three explicitly tracked report artifacts and the benchmark
artifact carry their provenance; synthetic artifacts must remain labelled synthetic.

## API

- `evaluate(extraction, profiles, interpretations=None)` returns `EngineOutput`.
- `analyze_nutrition(extraction)` returns normalized nutrition and a deterministic consistency check, or None.
- `explain_term(term, lang="en")` performs KB lookup; unknown/multi-term input returns None.
- `restriction_catalog()` returns fresh contract objects for all 29 restrictions.
- `category_vocabulary()` returns a fresh copy of the frozen category vocabulary.

Contract classes are imported from `shared`; no alternative contract is defined.
Report summaries remain empty for Part 2. Explanations stay English; wire parameters
keep canonical category/nutrient/basis IDs and exact ingredient/statement text.

## Matching and rules

The KB contains **260 entries**. Import validates every file, category, alias, code
and catalog key. Hindi/Telugu combining marks survive normalization. Codes retain
their letter and Roman suffixes; an unknown suffix is unresolved, not silently
treated as a known parent additive. Qualifiers apply to the attached item, not to
the next code across a comma. A generic plant source does not rule out soy.

Longest non-overlapping aliases protect compounds such as cocoa butter, peanut
butter, coconut milk and almond milk. Other recognized words in the same ingredient
still match. Fuzzy fallback uses token_sort_ratio >=92 with aliases at least five
characters; a second score repairs OCR-inserted spaces before applying that same
threshold. Unrecognized residual content is returned in unresolved_terms.
Structured sub-ingredients are matched recursively. Unreadable ingredients are
excluded from matching and prevent an absence conclusion.

Signals follow master-spec section 9 order. Conflict beats possible, then unknown,
then not_listed. A trace warning with preference severity is only not_listed when
the ingredient section supports absence; otherwise the trace is preserved as
supporting evidence on an unknown result. All signals are kept in matches, with
worst-state evidence first. Missing locations become explicit unverified evidence.
Confidence follows the shared rules, including the 0.2 unverified-only penalty.

## How the four states are decided (master spec §9)

For every restriction, collect all relevant signals and choose the worst:
**conflict → possible → unknown → not_listed**. A positive readable signal still
counts when another part of the label is missing. The first signal of the worst
state in the table order supplies the main reason. Its evidence comes first;
other supporting evidence and all matches remain available.

| Signal or situation | Decision in plain words |
| --- | --- |
| Readable ingredient or child with a definite matching KB category | **Conflict**. The named ingredient conflicts with the restriction. |
| An unresolved possible source in the KB | **Check this** (`possible`). Resolve it only with an applicable printed source qualifier or the limited green-mark rule. |
| Unknown term interpreted by the LLM as a relevant category | **Check this**, never conflict. Interpretation cannot replace a resolved KB ingredient. |
| Sugar/hidden-sugar ingredient for `diabetes_sugar` | **Check this**; the quantitative threshold can supply conflict. |
| “Contains” statement with a definite matching item | **Conflict**. Ambiguous mappings retain possible categories, e.g. “nuts” does not definitely identify peanut. |
| “May contain” or “facility” statement, strict severity | **Check this**. |
| “May contain” or “facility” statement, preference severity | **Not listed** plus the trace note, only when ingredient-section completeness supports absence; otherwise unknown. |
| Brown/non-veg mark and a restriction covering meat, poultry, fish-derived, egg-derived, gelatin or animal-derived categories | **Conflict**. |
| Green/veg mark | Resolves ambiguity only for those six categories. It says nothing about dairy, honey, insects, onion, garlic or root vegetables. |
| Readable, nonsuspect nutrient above the requested maximum at the requested basis | **Conflict**. Convert compatible per-serving/per-100 bases when needed. |
| Readable, nonsuspect nutrient equal to or below the maximum | **Not listed / within limit** for that threshold signal. |
| Required nutrient row/value missing or unreadable | **Unknown / can't determine** (`undeterminable`). |
| Required nutrient flagged as suspect by the consistency check | **Unknown / can't determine**; do not use the number for a threshold. |
| No nutrition table | **Unknown / can't determine** for a threshold. |
| Unknown restriction key or information not available from labels | **Unknown / can't determine**; never guess or crash. |
| No deciding signal and ingredient section missing | **Unknown / can't determine**. |
| No deciding signal, complete ingredient section and every ingredient readable | **Not listed**. For vegetarian/eggetarian with a green mark, include that evidence. |
| No deciding signal and the section is truncated | **Unknown / not detected**: nothing relevant found in the readable part. |
| No deciding signal and some ingredients are unreadable | **Unknown / not detected**. |

An explicit conflict always beats a green mark. If the list says egg while the
mark is green, the result remains conflict with an “internally inconsistent label”
note. A green mark alone cannot establish absence from an incomplete list.

Threshold-only restrictions such as low sodium use threshold rows only.
`diabetes_sugar` combines the threshold with sugar ingredients: a sugar alias can
keep the result possible even if a separate threshold signal is within limit or
unknown. A missing allergen statement produces an informative UnknownItem; it does
not by itself negate an otherwise complete ingredient-section assessment.

Each profile's overall state is the worst restriction result. With no profiles,
reports are empty but extraction analysis is still returned. A profile with no
restrictions has no results and uses not_listed as the empty aggregation identity;
the UI should say “no restrictions configured.” It is not a substantive food check.

Confidence is 1.0 for KB/statement/threshold signals, 0.7 for source ambiguity and
model confidence ×0.8 for model interpretations. Deduct 0.2 when all collected
evidence is unverified. These are engine signal scores, not calibrated probabilities.

Green marks resolve only the specified slaughter-derived ambiguities. They cannot
override explicit egg or other conflicting ingredients. Milk, honey, insects,
onion, garlic and root-vegetable restrictions are not resolved by green marks.
Untrusted model interpretations use the fixed vocabulary and valid 0..1 confidence;
their signals never exceed possible and cannot reclassify a resolved KB ingredient.

## Nutrition and suspect readings

Normalize per-serving/per-100/per-pack values only across compatible mass or volume
bases. Salt is converted to sodium and kJ to kcal. Printed values are preserved.
The engine checks energy against 4*protein + 4*carbohydrate + 9*fat, including the
specified 2.4*polyols term when an `other` row is labelled Polyols. Fibre is subtracted
only when the carbohydrate row explicitly says it includes fibre.

Energy deviation up to 15% is accepted. Larger deviations trigger single-field
hypotheses (x10, /10, missing decimals, 0/8, 1/7 and 5/6 substitutions). All plausible
fields that can bring the mismatch within 5% are suspect; if none can, all four
core fields are suspect. No hypothesis changes an extracted value. Serving-ratio checks allow discrepancies explained by printed rounding, including very small values rounded to zero. Sugar/carbohydrate,
saturated/total-fat, added/total-sugar, duplicate-value and serving-ratio checks also
feed suspect_keys. Status follows the energy check; independent sanity suspects can exist even with status consistent. Thresholds skip suspect fields. Missing macros produce
insufficient_data, with any independently detected sanity suspects retained.

## Extending the KB

`KB_REVIEW.md` lists every medium-confidence, possible-category, variable-origin or
explicitly flagged entry, plus every Hindi/Telugu alias for native-speaker review.
Regenerate it with `python -m engine.kb_review`. Generic albumin has possible egg
categories; explicit ovalbumin/egg albumen remain definite egg. Combining vowel
marks count as word content, preventing aliases from matching inside Indic words.
These fixes were found independently; no real packet corpus was available.

Add entries to `kb/terms.json` using the existing Pydantic schema. Give each entry a
unique id, aliases, origin, notes, and only contract categories. The optional
`review_reason` field records a concrete human review question; explanations
surface it as a caution even when the ingredient identity is high confidence.
Entries with possible_categories require origin varies; contested entries need medium confidence
and explicit notes. Add verified codes only; suffixes are significant. Add a
qualifier with a narrow term_ids scope when a printed source genuinely resolves an
ambiguity. Never add vague translations without review. Run the full tests.

Reference checks used the [Codex GSFA additive index](https://www.fao.org/gsfaonline/additives/index.html?lang=en)
and [FAO JECFA specifications](https://www.fao.org/food/food-safety-quality/scientific-advice/jecfa/jecfa-additives/en).
These identify additives; an identifier alone does not establish feedstock origin,
allergen concentration, legal authorization, or personal diet practice. The
[Allergy UK lactose guidance](https://www.allergyuk.org/resources/lactose-intolerance/)
also distinguishes similarly named non-lactose ingredients. See DECISIONS.md and
NOTES_FOR_OTHERS.md for taxonomy limitations and review items.

## Evaluation

See `eval/dataset/README.md` for human truth collection and fixed profiles. Run:

```
python -m engine.eval.run_eval --responses engine/eval/responses
```

For the final live capture (backend must already run with `ENGINE_MODE=real`):

```
python -m engine.eval.run_eval --backend http://localhost:8000 --responses engine/eval/responses/final_live
```

Real packet folders are `engine/eval/dataset/<case_id>/truth.json` plus contiguous
`img_0.jpg`–`img_2.jpg` panels, at most 2000 px on the longest edge and 400 KB each.
Keep clean and deliberately imperfect photos in separate cases. Human truth must
come from the packet/photos, not from engine predictions. The dataset guide contains
the complete JSON format and the eight fixed profiles.

Saved responses must use the profile IDs in `eval/eval_profiles.json`. The runner
writes report.json, report.md and metrics.json. It scores ingredient precision/recall,
nutrients, statements, veg marks, four-state verdicts, dangerous misses, evidence,
unknowns and latency, with its present scoring limitations recorded in the report.
It rejects empty and mixed real/synthetic datasets. Annotated printed rounding and per-100 mass/volume units are supported. No real-packet accuracy has been measured yet.

`report.md` has extraction-accuracy tables, a four-state confusion matrix, dangerous
misses, evidence/unknown rates, measured request latency, error attribution and scope.
`report.json` retains full audit metrics, per-case scores, fingerprints and reviews.
The small `metrics.json` is the About-page handoff: `{status, metrics, generated_at}`.
The numeric fields inside `metrics` are packets, ingredient_recall,
ingredient_precision, nutrient_accuracy, verdict_accuracy, dangerous_miss_rate,
evidence_verified_rate, unknown_rate and avg_latency_s. Rates are fractions, time is
seconds, and null means unmeasured. generated_at is UTC artifact-generation time.
See `NOTES_FOR_OTHERS.md` for the exact owner handoff and UI formatting requirements.

Only nonempty real runs publish `status: ready`. Synthetic runs publish pending,
zero real packets and null headline values; their detailed software-check scores
remain in report.json/report.md. Request latency comes from capture_manifest.json,
including cache hits (counted in the detailed report). Extraction-only duration_ms
and offline replay do not measure the complete backend request, so their headline
latency is null. Failed capture/missing response files abort scoring.

Two fixture-derived cases and their reports are checked in under `eval/synthetic/` and `eval/reports/`. To reproduce:

```
python -m engine.eval.build_synthetic
python -m engine.eval.run_eval --dataset engine/eval/synthetic/dataset --responses engine/eval/synthetic/responses --classifications engine/eval/synthetic/classifications.json --reports engine/eval/reports/synthetic_before
python -m engine.eval.run_eval --dataset engine/eval/synthetic/dataset --responses engine/eval/synthetic/responses --classifications engine/eval/synthetic/classifications.json --reevaluate --baseline engine/eval/reports/synthetic_before/report.json
```

The report is labelled synthetic, has zero real packets, and includes a deliberate carbohydrate misread. Real collection uses `engine/eval/dataset/<case_id>/truth.json` with `img_0.jpg` (up to three panels), plus `engine/eval/responses/<case_id>.json`; see the dataset guide for the complete format and clean/imperfect pairing.

## Performance

Benchmark the largest saved real extraction after capture:

```
python -m engine.eval.benchmark --responses engine/eval/responses/final_live --output engine/eval/performance.json
```

Largest means most ingredient-name characters, including children. The benchmark
uses eight fixed profiles, 10 warmups and 300 timed calls, and reports median, p95,
maximum, Python version and platform. The <50 ms target is checked at p95. Timing
excludes import, JSON parsing, HTTP, OCR, models and browser work.

No real extraction is currently available, so that target is **unmeasured**.
The explicit fixture-only check (`python -m engine.eval.benchmark --fixture`) measured
**5.34 ms median, 5.65 ms p95, 6.10 ms maximum** for 11 ingredient nodes and eight
profiles on macOS arm64 / Python 3.13.9. Raw measurements and method are in
`eval/performance.json`. A fixture timing does not satisfy the largest-real-label check.

## Honest limitations and feature freeze

- No real-packet accuracy, dangerous-miss or live latency claim is supported yet.
  The checked-in detailed report uses two synthetic cases; a zero synthetic miss
  count does not establish zero engine-caused misses on real food labels.
- The engine trusts section completeness, extracted words and evidence status
  supplied by Part 2. A false “complete” list can hide an extraction omission.
  Verified evidence means OCR alignment, not independent confirmation of the packet's composition.
- The 260-entry KB and >=92 fuzzy matching are finite coverage, not exhaustive
  language or ingredient understanding. Unknown fragments remain unresolved.
  Hindi/Telugu aliases and 38 source/taxonomy/practice review entries need human review.
- The frozen lactose catalog is a broad milk-origin screen; it does not distinguish
  lactose-free milk or residual milk protein. Spec-required maltodextrin/date-paste
  sugar categories and lactitol milk categories have taxonomy limits recorded in
  KB_REVIEW.md. They are not chemical, regulatory or clinical measurements.
- Community practice differs for some Jain ingredients and additive sources.
  Possible categories remain possible; no additive code establishes manufacturing origin.
- Nutrition checks identify inconsistencies and suspect fields; they never repair
  readings automatically. Missing macros limit the check, and compatible erroneous
  numbers can pass 4/4/9. No density or unreadable quantity is inferred.
- Evaluation currently scores top-level ingredient text with one-to-one fuzzy >=85,
  nutrients within max(2%, human-annotated rounding), exact statement sets and
  profile-overall verdicts. It does not prove image-coordinate accuracy or count
  distinct physical products. Human truth/provenance is not independently certified.
- Panel deduplication belongs to Part 2. Engine tests preserve duplicate evidence
  from both panels and independently readable children under an unreadable parent.
- No verdict rules or KB entries changed during Phase 4. The public API remains
  deterministic and offline; clock/network access exists only in evaluation tooling.

Follow-up review fixed two dangerous matcher defects: list splitting now preserves
original offsets through Unicode expansion, and fuzzy repair cannot discard an
unrelated exact allergen. Interrupted capture batches are marked pending and cannot
be scored as complete. These repairs add no verdict rules. The expanded suite has
590 passing tests; [final verification](eval/FINAL_VERIFICATION.md) records the
adversarial cases and remaining real-data validation limits.

See [Phase 4 measurement status](eval/PHASE4_STATUS.md) for current blockers and
what can honestly go into the pitch. This package reports label evidence and its
limits; none of its four states is a guarantee about the food.
