# Phase 1 decisions

- Implement only inside engine; the supplied folder initially had no Git metadata. After the human supplied VBodduku/labellens, attach the initial local part-3-engine branch to its existing remote commit without checking out or rewriting project files.
- Phase 1 delivers the complete ingredient/statement/completeness rows plus usable basic threshold/nutrition APIs; full consistency and suspect-value diagnosis remain Phase 2.
- Copy all frozen catalog entries unchanged and append celery, lupin and mollusc restrictions so all 15 allergen categories are selectable.
- Cache typed KB records once; use frozen term models/tuple fields, read-only lookup indexes and defensive public catalog/vocabulary copies.
- Retain exact INS suffixes and explicitly list known variants; unknown variants remain unresolved rather than silently inheriting a base code.
- In addition to token_sort_ratio >=92, remove OCR-inserted spaces for a second ratio at the same threshold; this resolves the specified pea nuts and whey pow der examples.
- Whole-word matching collects non-overlapping aliases longest first, preserving separate signals in a compound ingredient while protecting plant milk/butter names.
- A generic plant-source qualifier does not exclude soy; only a specific sunflower source resolves lecithin away from soy.
- Negated source phrases never become affirmative qualifiers; keep the additive ambiguous and expose unresolved residual wording for review.
- Preference trace warnings cannot produce not_listed from an incomplete ingredient section; retain the trace as supporting evidence on unknown.
- Missing evidence produces a verbatim unverified Evidence record; no box or verified location is invented.
- Partially readable ingredients may supply a positive signal but prevent absence; fully unreadable parents and children are skipped.
- Unresolved residual text remains available for model interpretation even when other parts of the ingredient matched; resolved KB ingredients cannot be reclassified by model input.
- Model interpretations must match the unresolved term, use only CATEGORIES, and have finite confidence within 0..1; invalid input is ignored and stays unresolved.
- Unknown terms on a complete ingredient list follow the specified completeness semantics; an unmapped term alone does not imply a particular restriction category. unresolved_terms exposes that limitation.
- Green marks resolve only the exact slaughter-derived category set in the master spec, never milk/dairy, honey, insects or Jain plant categories.
- Mark dried ginger/turmeric diet-practice ambiguity as possible root_vegetable with notes; fresh ginger is definite per the spec.
- Use the requested sugar-signal taxonomy for maltodextrin/date paste, with notes that this is not a chemical or regulatory added-sugars classification.
- Use the requested milk-origin mapping for lactitol, with explicit notes that origin does not establish residual allergenic protein or lactose content.
- Avoid uncertain vernacular equivalents for celery, lupin and molluscs; English aliases are supported and regional-name review is still needed.
- INS 441 is retained as the specified legacy gelatin label code; code recognition does not assert current regulatory authorization. E472f likewise is a label identifier, not an authorization claim.
- No mass/volume conversion without density; only matching g/ml serving and pack bases can be converted. Invalid units, unreadable, negative or nonfinite amounts are not compared.
- Inconsistent duplicate nutrition readings stay unusable; later duplicates cannot silently restore a conflicting value.
- Start the evaluation harness with offline saved responses; exclude the template and refuse empty-data accuracy reports. Backend upload mode is Phase 2.
- Evaluation uses one-to-one ingredient matching, a documented 2%/0.05-unit nutrient tolerance, exact normalized statement sets and unknown for missing profile reports; undefined rates are null.

# Phase 2 decisions

- Single-field correction hypotheses identify suspect fields and never rewrite label values; keep every plausible field when the diagnosis is ambiguous, otherwise mark all four core fields.
- Compute deviation relative to declared energy; zero/zero is consistent, and positive macros with zero energy are inconsistent with an undefined (null) percentage.
- The frozen contract represents polyols with key other and raw_label Polyols/Sugar alcohols; an internal polyols_g key participates in the formula and is not added to the public nutrient vocabulary.
- Subtract fibre only when the carbohydrate row explicitly says including/includes fibre; the default does not subtract fibre.
- Sanity checks flag both sides of impossible part/whole relationships because the label alone cannot identify which side was misread.
- A printed serving value differs by more than 10% of its expected value before it becomes suspect; a value exactly on the boundary is accepted.
- Derive servings per pack only from positive finite compatible pack/serving sizes when the explicit count is missing; never infer density.
- A concrete NutritionTable supplies readable signals even if stale section metadata says not_found, matching the ingredient-rule principle that positive evidence survives incomplete sections.
- A green mark inconsistency note applies to every affected restriction, including an egg allergy, rather than only diet-category matches.

- If a formula explicitly requires fibre or a declared polyol row but its value is unreadable, return insufficient_data instead of assuming zero.
- Preserve exact printed nutrient labels but strip their unit suffix for matching, so Salt (g) still converts to sodium rather than being treated as sodium mass.
- Expand the KB to 224 distinct ingredient entries; retain soy-sauce wheat/gluten variability as possible, and add no unverified additive numbers.
- Evaluation truth optionally records per-100 g/ml units and an absolute printed-rounding tolerance; mismatched mass/volume analyses do not score as correct nutrients.
- Evaluation reports carry dataset_kind; reject mixed real/synthetic runs, and leave synthetic latency unmeasured. The two synthetic cases retain manual expectations and one deliberate extraction error.
- Keep generated synthetic examples and report artifacts in Git for reproducibility, while ignoring real images and local responses until human review.

- Phase 2 supersedes the Phase 1 parent-skip policy: an unreadable parent name is skipped, but independently readable structured children still match and can conflict.

- Serving-ratio checks accept either the 10% range or a discrepancy explained by printed last-digit rounding (the larger allowance, not their sum). This preserves the fixture's legitimate 0.1 g per-100 / 0.0 g per-serving trans-fat rounding.

- A green-mark ambiguity resolution is supporting evidence, not a competing verdict signal; explicit trace notes retain their table-order reason when absence is otherwise justified.

- Consistency status follows the specified 15% energy rule. Independent sanity failures still populate suspect_keys even with status consistent; threshold checks always inspect those keys.

- Compile the entire alias-pattern tuple once at import: the expanded KB exceeded Python's implicit regex cache, so per-ingredient string-pattern matching regressed beyond 50 ms. Immutable compiled patterns preserve matching semantics and remove that cost.

- Phase 3: network capture lives only in the explicit evaluation CLI, with bounded requests and real-engine health checks; core engine imports/evaluation remain offline.
- Preserve raw scan responses for fixed-extraction replay. Require original LLM interpretation sidecars when needed instead of inferring model confidence/categories from verdicts.
- Before/after comparisons require identical case IDs, truth, photo bytes and profiles. Local code fingerprints cannot attest which code a separate backend process has loaded.
- Error causes require explicit reviewed explanations; engine-owned classifications require regression-test references. Unreviewed dangerous misses make the engine-caused count unmeasured, not zero.
- Missing expected profiles always fail verdict accuracy, including expected unknown; confusion-matrix fallback remains unknown and missing IDs are separately counted.

- Phase 3 KB has 260 entries; common Hindi/Telugu ingredient aliases are included but still require native-speaker and packet-use review. No new additive numbers were added.
- Correct generic albumin from definite egg to possible egg/egg-derived (medium); explicit ovalbumin and egg albumen remain definite egg. Albumin is a protein family, not an exclusive egg-source label.
- Whole-word boundaries treat Unicode combining marks as word content so Hindi/Telugu vowel signs cannot split a syllable. Existing >=92 fuzzy policy is retained.
- Add optional internal review_reason metadata and generate KB_REVIEW.md from every medium, possible, variable-origin or flagged entry. High-confidence origin taxonomy limitations are flagged without silently changing spec-required lactitol/sugar categories.

- Phase 4 feature freeze: no KB or verdict-rule changes. Edge cases cover empty/no-profile/no-restriction inputs, nested-only and duplicate panel ingredients, unknown keys and extreme/nonfinite nutrient readings.
- About metrics retain Part 1's existing status/metrics envelope. Only real case measurements populate numeric rates; synthetic runs publish pending, zero real packets and null rates. generated_at is UTC artifact-generation time, not evidence of a live scan.
- Request latency comes from capture_manifest request_ms, with cache hits disclosed. Extraction-only duration_ms and engine replay cannot establish request latency; leave it null if no HTTP timings were captured.
- Performance benchmark explicitly distinguishes largest saved real extraction from opt-in fixture timing; fixture timing cannot satisfy the real-label acceptance target. Largest is measured by ingredient-name characters including children; report warm median/p95/max and environment.

- Freeze follow-up: split ingredient lists using original character offsets while normalizing delimiter candidates; whole-string NFKC/lowercase offsets can truncate a following allergen. Exact label text remains intact.
- Freeze follow-up: a full-fragment fuzzy compound repair may replace exact spans only if those spans are part of the candidate compound. It must not discard an unrelated exact allergen such as egg after a long misspelled additive name.
- Mark a capture batch pending before writing any responses. Interrupted recaptures must block offline scoring even if a previous successful manifest and old responses exist.

## Known taxonomy limitations (need human review)
- The frozen lactose catalog maps to milk, which cannot distinguish lactose-free milk, low-lactose cheeses or low-lactose clarified butter. This is a broad origin screen; correcting that clinically imprecise taxonomy needs a human-approved contract/catalog design decision on main.
- The requested sugar_alias/added_sugar taxonomy includes maltodextrin and date paste; neither should be presented as a precise chemical or regulatory added-sugar claim. Existing message template says "a form of sugar"; a more accurate future template would say "an ingredient to check against the sugar value". Request for main only; shared files were not changed.
- Phase 3 corrects generic albumin to possible egg/egg-derived: it does not establish an egg source. Explicit egg albumen/ovalbumin remain definite egg. KB_REVIEW.md records the source references and pending human review.
- Lactitol is lactose-derived but its inclusion under milk does not establish allergenic protein; confirm whether broad milk-origin screening is the intended profile behavior.
- Regional names for celery/lupin/molluscs remain intentionally unfilled rather than inventing ambiguous translations. Hindi/Telugu names exist for common Indian allergens; native-speaker review is still needed.
- Dried ginger/turmeric Jain acceptance, ambiguous additive origins, spice blends and flavour sources carry medium-confidence notes and possible categories for review. Lecithin without source includes possible soy/egg; plant source alone leaves possible soy.
