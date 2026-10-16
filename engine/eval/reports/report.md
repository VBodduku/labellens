# Synthetic pipeline check — NOT real-packet accuracy

| Metric | Value |
| --- | --- |
| dataset_kind | synthetic |
| packets | 2 |
| real_packets | 0 |
| ingredient_precision | 1.0 |
| ingredient_recall | 0.9545454545454546 |
| nutrient_accuracy | 0.9375 |
| statement_accuracy | 1.0 |
| veg_mark_accuracy | 1.0 |
| verdict_accuracy | 0.9375 |
| dangerous_misses | 0 |
| expected_conflicts | 9 |
| dangerous_miss_rate | 0.0 |
| evidence_verified_rate | 0.9571428571428572 |
| unknown_rate | 0.1875 |
| missing_profile_count | 0 |
| average_latency_ms | None |
| latency_samples | 0 |
| error_count | 3 |
| unreviewed_error_count | 0 |
| unreviewed_dangerous_misses | 0 |
| engine_dangerous_misses | 0 |
| extraction_dangerous_misses | 0 |

Confusion matrix (rows expected, columns predicted):

```json
{
  "conflict": {
    "conflict": 8,
    "possible": 1,
    "unknown": 0,
    "not_listed": 0
  },
  "possible": {
    "conflict": 0,
    "possible": 3,
    "unknown": 0,
    "not_listed": 0
  },
  "unknown": {
    "conflict": 0,
    "possible": 0,
    "unknown": 3,
    "not_listed": 0
  },
  "not_listed": {
    "conflict": 0,
    "possible": 0,
    "unknown": 0,
    "not_listed": 1
  }
}
```

- Synthetic fixtures test software behavior only; they do not measure real-packet accuracy.
- Nutrient tolerance is max(2% of truth, annotated absolute printed rounding); no unannotated rounding allowance.
- Statements use exact normalized item sets; ingredients use top-level items with one-to-one fuzzy matching >=85.
- Missing expected profiles appear as unknown in the confusion matrix, always fail verdict accuracy, and are listed; missing responses abort the run.
- Evidence rate counts unique extraction evidence records, including nested ingredients, claims and veg marks.
- Unknown rate uses restriction results in supplied reports. Verdict accuracy uses expected profile overalls.
- Latency uses positive saved extraction durations for real packets only; synthetic latency is unmeasured.
- Saved extractions were re-evaluated with the current local engine and exact profiles; saved input responses remain unchanged.
- Replay is not a new extraction run and has no measured scan latency. Missing original LLM inputs block replay rather than silently dropping model signals.
- Error causes are unreviewed until explicitly classified with an explanation; engine-owned classifications require a regression-test reference.
- The local engine fingerprint identifies this checkout, not the code loaded by a separate backend process. Restart the backend after engine changes; health only confirms ENGINE_MODE=real.

Source mode: reevaluated. Local engine fingerprint: a0456448ccd6bc672c869c7945da6007e760900f99685249cdc8a85ab3f3d922.

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

## Error analysis

| Error ID | Check | Expected | Predicted | Classification | Review |
| --- | --- | --- | --- | --- | --- |
| synthetic_imperfect:ingredient_missing:1 | ingredient_missing | Peanuts (22%) | None | extraction | Controlled synthetic corruption, not a real observation: build_synthetic.py marks the fixture's peanut item unreadable. The scorer excludes unreadable ingredients; the engine correctly returns unknown for the incomplete peanut evidence. |
| synthetic_imperfect:nutrient:carbohydrate_g | carbohydrate_g | 58.0 | 5.8 | extraction | Controlled synthetic corruption, not a real observation: build_synthetic.py replaces 58 g carbohydrate with 5.8 g. The engine flags the inconsistent nutrition and preserves the extracted value rather than inventing a correction. |
| synthetic_imperfect:verdict:diabetes_sugar | verdict:diabetes_sugar | conflict | possible | extraction | The deliberately corrupted carbohydrate value makes the 38 g sugar reading exceed 5.8 g carbohydrate. Both part/whole readings become suspect; threshold conflict is withheld and the deterministic sugar alias leaves possible. This is the required conservative response to the synthetic extraction fault, not a rule bug. |
