# Synthetic pipeline check — NOT real-packet accuracy

Generated: 2026-10-16T12:42:18Z. Cases: 2; real cases: 0.

**No real-packet headline metrics are available.** These fixture-derived software checks cannot substantiate a pitch accuracy claim. About-page metrics remain pending, with zero real packets and null rates.

## Extraction accuracy

| Measure | Accuracy |
| --- | ---: |
| Ingredient precision | 100.00% |
| Ingredient recall | 95.45% |
| Nutrient values | 93.75% |
| Allergen statements (exact sets) | 100.00% |
| Veg mark | 100.00% |

## Verdicts, evidence and unknowns

| Measure | Value |
| --- | ---: |
| Verdict accuracy (profile overall) | 93.75% |
| Dangerous-miss rate | 0.00% (0 / 9 expected conflicts) |
| Engine-caused dangerous misses | 0 |
| Extraction-caused dangerous misses | 0 |
| Unreviewed dangerous misses | 0 |
| Evidence verified rate | 95.71% |
| Unknown rate (restriction results) | 18.75% |
| Missing expected profiles | 0 |

A dangerous miss is expected conflict → predicted not_listed. Conflict → possible/unknown also fails verdict accuracy; inspect the matrix and error audit.

## Verdict confusion matrix

Rows are expected states; columns are predicted states.

| Expected / predicted | conflict | possible | unknown | not_listed |
| --- | ---: | ---: | ---: | ---: |
| conflict | 8 | 1 | 0 | 0 |
| possible | 0 | 3 | 0 | 0 |
| unknown | 0 | 0 | 3 | 0 |
| not_listed | 0 | 0 | 0 | 1 |

## Latency

| Measure | Value |
| --- | ---: |
| Mean backend request duration | unmeasured |
| Timed requests | 0 |
| Cache hits in timed requests | 0 |

Measured by the capture client, including upload and backend response work; browser capture/render time is excluded. Saved extraction-only durations and offline replays are not end-to-end request measurements. Cache hits remain included and are counted above.


## Before / after (same truth and profiles)

| Metric | Before | After | Change |
| --- | --- | --- | --- |
| ingredient_precision | 1.0000 | 1.0000 | 0.0000 |
| ingredient_recall | 0.9545 | 0.9545 | 0.0000 |
| nutrient_accuracy | 0.9375 | 0.9375 | 0.0000 |
| statement_accuracy | 1.0000 | 1.0000 | 0.0000 |
| veg_mark_accuracy | 1.0000 | 1.0000 | 0.0000 |
| verdict_accuracy | 0.9375 | 0.9375 | 0.0000 |
| dangerous_misses | 0 | 0 | 0.0000 |
| dangerous_miss_rate | 0.0000 | 0.0000 | 0.0000 |
| evidence_verified_rate | 0.9571 | 0.9571 | 0.0000 |
| unknown_rate | 0.1875 | 0.1875 | 0.0000 |
| average_latency_ms | unmeasured | unmeasured | unmeasured |

Comparison rates above are fractions (0–1); latency is milliseconds. Both runs use the same truth, photos and profiles.

## Error analysis

| Packet / error ID | Check | Expected | Predicted | Cause | Review |
| --- | --- | --- | --- | --- | --- |
| synthetic_imperfect:ingredient_missing:1 | ingredient_missing | Peanuts (22%) | unmeasured | extraction | Controlled synthetic corruption, not a real observation: build_synthetic.py marks the fixture's peanut item unreadable. The scorer excludes unreadable ingredients; the engine correctly returns unknown for the incomplete peanut evidence. |
| synthetic_imperfect:nutrient:carbohydrate_g | carbohydrate_g | 58.0 | 5.8 | extraction | Controlled synthetic corruption, not a real observation: build_synthetic.py replaces 58 g carbohydrate with 5.8 g. The engine flags the inconsistent nutrition and preserves the extracted value rather than inventing a correction. |
| synthetic_imperfect:verdict:diabetes_sugar | verdict:diabetes_sugar | conflict | possible | extraction | The deliberately corrupted carbohydrate value makes the 38 g sugar reading exceed 5.8 g carbohydrate. Both part/whole readings become suspect; threshold conflict is withheld and the deterministic sugar alias leaves possible. This is the required conservative response to the synthetic extraction fault, not a rule bug. |

## Scope and limitations

- Synthetic fixtures test software behavior only; they do not measure real-packet accuracy.
- Nutrient tolerance is max(2% of truth, annotated absolute printed rounding); no unannotated rounding allowance.
- Statements use exact normalized item sets; ingredients use top-level items with one-to-one fuzzy matching >=85.
- Missing expected profiles appear as unknown in the confusion matrix, always fail verdict accuracy, and are listed; missing responses abort the run.
- Evidence rate counts unique extraction evidence records, including nested ingredients, claims and veg marks.
- Unknown rate uses restriction results in supplied reports. Verdict accuracy uses expected profile overalls.
- Latency uses positive capture-client request durations for real packets only. Saved extraction-only timings, synthetic cases and offline replay have no measured request latency.
- Saved extractions were re-evaluated with the current local engine and exact profiles; saved input responses remain unchanged.
- Replay is not a new extraction run and has no measured scan latency. Missing original LLM inputs block replay rather than silently dropping model signals.
- Error causes are unreviewed until explicitly classified with an explanation; engine-owned classifications require a regression-test reference.
- The local engine fingerprint identifies this checkout, not the code loaded by a separate backend process. Restart the backend after engine changes; health only confirms ENGINE_MODE=real.

Source mode: reevaluated. Local engine fingerprint: a0456448ccd6bc672c869c7945da6007e760900f99685249cdc8a85ab3f3d922.
Truth/photo fingerprint: 6c18435c632ae042cc9e7c46c9603b23eea099488cdeb692e733f15c802df906. Profiles fingerprint: cf3f8a7b6df71d2bcb965b447a5cebd098e311493ed5588dda4791727063653e.
