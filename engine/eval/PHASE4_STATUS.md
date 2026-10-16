# Phase 4 — feature freeze, real measurement incomplete

The final live run was attempted with:

```
python -m engine.eval.run_eval --backend http://localhost:8000 --responses engine/eval/responses/phase4_live
```

It exits 2: no real packet truth files are present (only `_template/truth.json`).
The local backend also refuses connections outside the sandbox. The humans were
asked to provide the packet folders and start the integrated server with ENGINE_MODE=real.
No real responses were captured and no real headline metric can be reported.

| Pitch-relevant measurement | Result |
| --- | --- |
| Real cases measured | 0 |
| Real ingredient / nutrient / verdict accuracy | Unmeasured |
| Real dangerous-miss / evidence / unknown rates | Unmeasured |
| Real backend latency | Unmeasured |
| evaluate() on largest real label (<50 ms target) | Unmeasured |
| Unit/integration tests | 590 passing, including shared fixture scenario and follow-up regressions |
| KB entries / catalog restrictions | 260 / 29 |
| New verdict rules / KB edits in this phase | None |

`reports/metrics.json` is the small existing-frontend-compatible envelope
`{status, metrics, generated_at}`: pending, zero real packets, null rates and latency.
It deliberately cannot present the synthetic test scores as real accuracy.
The concrete format and units are in `engine/NOTES_FOR_OTHERS.md` for Part 1/main;
the current About source accepts the envelope, but integrated UI verification and
owner review remain pending.

`reports/report.md` contains readable extraction, confusion-matrix, dangerous-miss,
evidence, unknown and latency tables for the two **synthetic** cases. Their software
check scores are unchanged: ingredient precision 100%, recall 95.45%, nutrient and
verdict accuracy 93.75%, dangerous misses 0/9 expected conflicts, evidence verified
95.71%, unknown restrictions 18.75%; request latency is unmeasured. All three known
synthetic discrepancies are deliberate extraction damage and remain documented.
These numbers cannot substantiate real-packet accuracy in the pitch.

The explicit fixture-only performance check used 11 ingredient nodes / 200 ingredient
characters, eight profiles/eight restrictions, 10 warmups and 300 timed calls:
median 5.3447 ms, p95 5.6530 ms, maximum 6.0957 ms on macOS arm64 / Python 3.13.9.
`performance.json` records the method and environment with `measurement_kind=fixture`
and `real_target_met=null`. This does not satisfy the largest-real-label target.

To finish, supply independently reviewed real cases in `engine/eval/dataset/<case_id>/`
(truth.json plus numbered photo panels), run the integrated backend, then run:

```
python -m engine.eval.run_eval --backend http://localhost:8000 --responses engine/eval/responses/final_live
python -m engine.eval.benchmark --responses engine/eval/responses/final_live --output engine/eval/performance.json
```

Review every discrepancy and dangerous miss before claiming an engine-caused count.
The complete collection format is in `dataset/README.md`; copy metrics.json to the
frontend only through its owner/main integration. Test count and KB coverage can go
into the pitch now; real accuracy and real-label performance cannot.
