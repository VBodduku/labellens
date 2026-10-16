# LabelLens engine — Phase 1

Pure deterministic Python, with the five functions specified in
`shared/engine_interface.py`. Run Python from the repository root. No network or
model calls occur when importing or evaluating the engine. The offline evaluation
runner also uses saved JSON only.

Create/activate a Python 3.11+ environment, then:

```
python -m pip install -r engine/requirements.txt
python -m pytest engine/tests
python -c "import engine; print(len(engine.restriction_catalog()))"
```

On this machine the task environment is `engine/.venv` (macOS/Linux activation:
`source engine/.venv/bin/activate`; Windows: `engine\.venv\Scripts\activate`).
No virtual environment, downloaded dependency, cache, or generated report belongs
in a commit. `engine/.gitignore` excludes these.

## API

- `evaluate(extraction, profiles, interpretations=None)` returns `EngineOutput`.
- `analyze_nutrition(extraction)` returns basic readable-value normalization or None.
- `explain_term(term, lang="en")` performs KB lookup; unknown/multi-term input returns None.
- `restriction_catalog()` returns fresh contract objects for all 29 restrictions.
- `category_vocabulary()` returns a fresh copy of the frozen category vocabulary.

Contract classes are imported from `shared`; no alternative contract is defined.
Report summaries remain empty for Part 2. Explanations stay English; wire parameters
keep canonical category/nutrient/basis IDs and exact ingredient/statement text.

## Matching and rules

The KB contains **157 entries**. Import validates every file, category, alias, code
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

Green marks resolve only the specified slaughter-derived ambiguities. They cannot
override explicit egg or other conflicting ingredients. Milk, honey, insects,
onion, garlic and root-vegetable restrictions are not resolved by green marks.
Untrusted model interpretations use the fixed vocabulary and valid 0..1 confidence;
their signals never exceed possible and cannot reclassify a resolved KB ingredient.

## Phase boundary

Ingredient, ambiguity, statement, completeness, precedence and confidence rules are
implemented and tested. Basic sugar/threshold comparisons, unit conversions,
per-serving to per-100, and per-pack calculations also work, so the public API and
fixture verdicts are usable immediately.

**Nutrition consistency diagnosis is not implemented in Phase 1.** The analysis
returns insufficient_data rather than asserting consistency. Macro-energy checks,
OCR correction hypotheses, cross-basis sanity checks, and full suspect-value
production are Phase 2 work. The rule can consume suspect_keys when that analysis
is added. Do not claim full master-spec nutrition acceptance yet.

## Extending the KB

Add entries to `kb/terms.json` using the existing Pydantic schema. Give each entry a
unique id, aliases, origin, notes, and only contract categories. Entries with
possible_categories require origin varies; contested entries need medium confidence
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

Saved responses must use the profile IDs in `eval/eval_profiles.json`. The runner
writes report.json, report.md and metrics.json. It scores ingredient precision/recall,
nutrients, statements, veg marks, four-state verdicts, dangerous misses, evidence,
unknowns and latency, with its present scoring limitations recorded in the report.
It rejects an empty real dataset. No real-packet accuracy has been measured yet.
