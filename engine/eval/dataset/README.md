# Human evaluation packets

Collect 10–15 varied real packets: a peanut product, dairy, a neutral ingredient list,
ambiguous emulsifiers, a Jain conflict, and at least one truncated or blurry photo.
Use one folder per product (`dataset/<id>/truth.json`, `img_0.jpg`, optional additional
panels). Keep the longest image side at most 2000 pixels and each image below 400 KB.
Do not commit images without team agreement.

Copy `_template/truth.json` and transcribe every visible ingredient and statement by
hand. Do not copy the scanner's output into the truth. Mark completeness based on the
photos, not on what is known about the product. Enter only readable per-100 nutrients.
Have a second person check the transcription and expected verdicts against the fixed
profiles in `../eval_profiles.json`. An ambiguous origin is `possible`; an unreadable
section cannot justify `not_listed`.

Save backend ScanResult responses as `<response_dir>/<id>.json`, generated using the
fixed evaluation profiles. Then run from the repo root:

```
python -m engine.eval.run_eval --responses engine/eval/responses
```

The runner scores saved responses, writes report.json/report.md/metrics.json, and
refuses to report accuracy on an empty dataset. Templates are excluded. Missing
profile reports count as unknown, with the IDs recorded. Latency is the saved
extraction duration, not the speed of reading files. Backend upload mode and more
precise printed-rounding annotations are deferred to Phase 2.

No real packets have been evaluated in Phase 1. Synthetic unit tests are not packet
accuracy measurements. Rates with zero denominators are null. The dangerous-miss
metric counts expected conflict predicted not_listed; also inspect the full matrix
for conflict-to-unknown and conflict-to-possible errors.
