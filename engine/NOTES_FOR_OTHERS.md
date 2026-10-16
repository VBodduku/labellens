# Integration and review notes

- Part 2: import engine's five functions directly using the frozen interface. Run from repo root and install engine/requirements.txt. All returns use shared contract models; report summary fields remain empty.
- Part 2: interpretations are keyed by unresolved term text; normalization permits different casing. Only unresolved fragments can receive LLM signals, capped at possible. Invalid categories or confidence are rejected without changing the deterministic result.
- Part 1: English explanations humanize canonical category/nutrient/basis IDs, while message_params retain the frozen translation conventions. Missing source locations are explicit unverified evidence without invented coordinates.
- Catalog adds celery/lupin/mollusc after all 26 unchanged fixture entries. These need normal catalog/i18n handling; no frozen contract change is needed.
- Part 2: nutrition consistency is implemented in Phase 2. Use consistency.status and suspect_keys to target re-reads; hypotheses never correct values automatically. Both consistent and insufficient_data can still contain suspects from independent sanity checks. Trigger a re-read for nonempty suspect_keys as well as status inconsistent; status summarizes the energy check, not all numeric sanity checks. Polyols use key other with raw_label Polyols; fibre inclusion must be explicit in the carbohydrate raw_label.
- The frozen lactose catalog maps to milk, which cannot distinguish lactose-free milk, low-lactose cheeses or low-lactose clarified butter. This is a broad origin screen; correcting that clinically imprecise taxonomy needs a human-approved contract/catalog design decision on main.
- The requested sugar_alias/added_sugar taxonomy includes maltodextrin and date paste; neither should be presented as a precise chemical or regulatory added-sugar claim. Existing message template says "a form of sugar"; a more accurate future template would say "an ingredient to check against the sugar value". Request for main only; shared files were not changed.
- Phase 3 corrects generic albumin to possible egg/egg-derived: it does not establish an egg source. Explicit egg albumen/ovalbumin remain definite egg. KB_REVIEW.md records the source references and pending human review.
- Lactitol is lactose-derived but its inclusion under milk does not establish allergenic protein; confirm whether broad milk-origin screening is the intended profile behavior.
- Regional names for celery/lupin/molluscs remain intentionally unfilled rather than inventing ambiguous translations. Hindi/Telugu names exist for common Indian allergens; native-speaker review is still needed.
- Dried ginger/turmeric Jain acceptance, ambiguous additive origins, spice blends and flavour sources carry medium-confidence notes and possible categories for review. Lecithin without source includes possible soy/egg; plant source alone leaves possible soy.
- The shared fixture's Lakshmi prose summary says "Probably fine"; engine does not copy or generate that summary. Part 2 should use the approved four-state wording when it generates its own summaries.
- Evaluation includes two synthetic cases and three reproducible report files. metrics.json carries dataset_kind=synthetic and real_packets=0: Part 1 must not present these as real-packet accuracy. Real collection uses engine/eval/dataset/<case_id>/truth.json plus img_0.jpg..img_2.jpg, with saved ScanResult responses in engine/eval/responses/<case_id>.json. Phase 3 adds explicit --backend capture and --reevaluate replay; see the dataset guide. Human photo/truth review and >=10 real packets remain outstanding.

- KB expanded to 224 distinct entries, with more milk derivatives, wheat forms, sugar aliases and Indian grains/pulses. Soy sauce has definite soy but only possible wheat/gluten; no new INS numbers were invented.
- Per-100 unit and optional printed rounding are recorded in evaluation truth; synthetic and real data cannot be combined in one report. Positive real extraction durations are used for latency; synthetic latency is null.

- Phase 3 input blocker (2026-10-16): this checkout contains no backend Python implementation and no real packet truth/photos; only the template is present. localhost:8000 refuses connections even outside the sandbox. origin/main was fetched but its integration commits are not in the current part-3-engine history; the human must synchronize the intended integration and start ENGINE_MODE=real. No branch switch or merge was performed by Part 3.
- Part 2: there are no packet-specific extraction findings yet because no real packet run was possible. Do not interpret this as zero extraction errors. Once data is supplied, errors are enumerated in report.json and require explicit extraction/KB/matcher/rule attribution.
- Part 2: preserve the original dict[str, TermInterpretation] in evaluation sidecars (<case_id>.interpretations.json) when saving scans. ScanResult alone does not retain the original model confidence/rationale needed for faithful fixed-extraction replay. No shared contract change was made.
- Restart the backend after engine edits: /api/health confirms real/stub mode, but the contract exposes no engine revision. The eval report's local code digest cannot prove which code a separate backend process loaded.
- KB_REVIEW.md currently has 38 source/taxonomy/community-practice review entries and a complete native-script alias table. These are pending review, not human-certified facts or real packet observations. The KB now has 260 entries.

## Phase 4 — About-page metric handoff (feature freeze)

Part 1 / main: the metric file is `engine/eval/reports/metrics.json`; copy it to
`frontend/public/metrics.json` during integration. The existing About loader on
origin/part-1-frontend expects `{status, metrics}`, so that envelope is preserved.
This is the concrete handoff format; no frontend file or frozen shared type was changed.

```json
{
  "status": "pending",
  "metrics": {
    "packets": 0,
    "ingredient_recall": null,
    "ingredient_precision": null,
    "nutrient_accuracy": null,
    "verdict_accuracy": null,
    "dangerous_miss_rate": null,
    "evidence_verified_rate": null,
    "unknown_rate": null,
    "avg_latency_s": null
  },
  "generated_at": "2026-10-16T00:00:00Z"
}
```

The timestamp above is a format example, not a measurement date. The generated
artifact contains the actual UTC generation time. `status` becomes `ready` only
for a nonempty real-packet evaluation. `metrics.packets` counts evaluated real
photo cases (clean and imperfect are separate cases, not unique physical products).
All rates are fractions 0–1; format as percentages in the UI. Null means unmeasured,
never 0%. `avg_latency_s` is the mean timed backend request in seconds, including
upload/backend response work, excluding browser capture/render. Cache hits remain
included; their count and timing sample count are in report.json/report.md.
Saved extraction-only durations and offline replay have null request latency.
`generated_at` is artifact-generation time; it is not proof of a fresh live scan.

Synthetic runs keep this file pending with zero packets and null values, while
their actual software-test scores remain in report.json/report.md. Never copy
synthetic scores into pitch claims. The existing About loader handles pending and
ignores nulls; Part 1 should add percent/seconds formatting and optionally display
the timestamp. Owner review of this handoff is still pending; compatibility was
checked against the existing source, not a running integrated frontend.

Part 2: panel merge owns ingredient deduplication. Engine regression tests preserve
duplicate evidence from both panels and still detect a readable child when a parent
name is empty/unreadable. A profile with no restrictions returns no checks and
overall not_listed as the empty aggregation identity; show "no restrictions configured"
in that UI case rather than presenting it as a substantive label assessment.
