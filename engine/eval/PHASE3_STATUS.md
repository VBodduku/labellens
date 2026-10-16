# Phase 3 measurement status — incomplete

Real-packet accuracy is **unmeasured**. This checkout has zero real packet cases.
It contains only `dataset/_template/truth.json`, and `localhost:8000/api/health`
refuses connections both inside and outside the sandbox. No backend Python files
are present. `origin/main` contains integration commits absent from this branch;
the agent did not merge or switch branches because AGENTS.md reserves merges for humans.

The requested command was attempted from the repository root:

```
python -m engine.eval.run_eval --backend http://localhost:8000
```

It exits 2 with “No real packet truth files ... No accuracy report generated.”
There are no real captured responses, extraction findings, live after measurements
or defensible claims of zero engine-caused dangerous misses.

| Real-packet metric | Before | Offline after | Live after |
| --- | --- | --- | --- |
| Cases measured | 0 | 0 | 0 |
| Ingredient recall | unmeasured | unmeasured | unmeasured |
| Nutrient accuracy | unmeasured | unmeasured | unmeasured |
| Verdict accuracy | unmeasured | unmeasured | unmeasured |
| Engine-caused dangerous misses | unmeasured | unmeasured | unmeasured |

Independent work completed: live capture, preserved-response replay, before/after
comparability checks, explicit error review, 260 KB entries, KB_REVIEW.md with 38
source/taxonomy/practice review entries and every Hindi/Telugu alias, generic albumin
ambiguity correction and Unicode combining-mark boundaries. These changes were not
derived from real packet observations.

Validation: `python -m pytest engine/tests` passes **497 tests**, including the shared
fixture scenario. Ruff and strict Mypy checks pass. Importing the engine returns
29 catalog restrictions. Real-data and live-backend validation remain outstanding.

`reports/report.md` is explicitly a **synthetic harness check**, comparing supplied
saved fixture-derived reports with current-engine replay of those same extractions.
It is not a before/after claim about real accuracy or about two live backend revisions.
The two synthetic cases retain 95.45% ingredient recall, 93.75% nutrient accuracy,
93.75% verdict accuracy and zero conflict-to-not_listed results before and after.
All three synthetic errors are explained in `synthetic/classifications.json` as
controlled extraction damage; no artificial “improvement” was created.

To reproduce that software check:

```
python -m engine.eval.run_eval --dataset engine/eval/synthetic/dataset --responses engine/eval/synthetic/responses --classifications engine/eval/synthetic/classifications.json --reports engine/eval/reports/synthetic_before
python -m engine.eval.run_eval --dataset engine/eval/synthetic/dataset --responses engine/eval/synthetic/responses --classifications engine/eval/synthetic/classifications.json --reevaluate --baseline engine/eval/reports/synthetic_before/report.json
```

To unblock the actual phase, humans must synchronize the integration into this
checkout, start the backend with ENGINE_MODE=real, and supply independently reviewed
packet folders at `engine/eval/dataset/<case_id>/truth.json` plus contiguous
`img_0.jpg`–`img_2.jpg` panels (≤2000 px longest edge, ≤400 KB each). Use separate
clean/imperfect case folders. The complete truth format and live/offline commands
are in [the dataset guide](dataset/README.md). Keep before responses and reports;
capture live after results into a separate response directory.
