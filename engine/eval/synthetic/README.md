# Synthetic cases only

These two saved responses derive from `shared/fixtures/scan_result.json`, evaluated
using all eight profiles in `engine/eval/eval_profiles.json`. They are simulations,
not photographs, real packets, or evidence of real-world accuracy.

- `synthetic_clean`: the original fixture extraction. Manual profile expectations
  follow the fixture and the master rules.
- `synthetic_imperfect`: a truncated list with unreadable peanuts, no readable
  allergen statement, an unclear veg mark, and a deliberately corrupted carbohydrate
  reading (5.8 instead of 58 g). Truth retains 58 g, independently of the prediction.
  The numeric sanity check withholds the sugar threshold and produces possible
  from the sugar aliases. The expected sugar conflict therefore appears as an
  expected-conflict/predicted-possible error in the matrix. The report is deliberately
  not a perfect-score demonstration.

Generate and score from the repository root:

```
python -m engine.eval.build_synthetic
python -m engine.eval.run_eval --dataset engine/eval/synthetic/dataset --responses engine/eval/synthetic/responses
```

The three files in `engine/eval/reports/` identify this as a synthetic pipeline
check with zero real packets and unmeasured latency. Do not use those numbers as
real-packet accuracy on the frontend or in a pitch. A separate real dataset must
replace them after human collection and review.
