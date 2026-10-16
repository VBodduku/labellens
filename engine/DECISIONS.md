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
