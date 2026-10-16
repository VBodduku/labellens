# Part 3 — Verdict engine, knowledge base and evaluation

**Machine:** System B (Mac) · **Tool:** Codex · **Branch:** `part-3-engine` (worktree folder `../labellens-part3`) · **Folder you own:** `engine/` only
**Read first:** `docs/00_MASTER_SPEC.md` (whole — **§9 Verdict semantics is your specification**), `shared/contract.py`, `shared/engine_interface.py`, `shared/messages.en.json`, `shared/fixtures/catalog.json`, `shared/fixtures/scan_result.json`.

You build the brain that decides, deterministically and testably, what a label means for each family member. No network, no LLM calls, no randomness. You never wait for anyone: your inputs are contract objects, and the fixtures give you realistic ones.

---

## 1. Goals

1. Implement every rule in master spec §9 exactly, with a test per row.
2. A knowledge base that understands how Indian packaged-food labels actually name things (hidden dairy, hidden sugar, INS codes, Jain rules, Indian-language names).
3. Nutrition normalisation and a **consistency check** that catches OCR misreads.
4. An **evaluation harness** that turns 10–15 real photographed packets into honest accuracy numbers for the pitch.

---

## 2. Public API (must match `shared/engine_interface.py` exactly)

`engine/__init__.py` exports module-level functions:

```python
def evaluate(extraction: LabelExtraction, profiles: list[Profile],
             interpretations: dict[str, TermInterpretation] | None = None) -> EngineOutput
def analyze_nutrition(extraction: LabelExtraction) -> NutritionAnalysis | None
def explain_term(term: str, lang: Lang = "en") -> ExplainResponse | None
def restriction_catalog() -> list[RestrictionCatalogItem]
def category_vocabulary() -> list[str]
```
Import contract types from `shared.contract` and `shared.engine_interface`. Pure functions; load the KB once (module-level cache) and treat it as read-only. `evaluate` must run in < 50 ms for a typical label.

---

## 3. Folder structure

```
engine/
├── __init__.py            public API above
├── README.md              how the rules work, how to extend the KB, how to run eval
├── requirements.txt       pydantic>=2, rapidfuzz, pytest
├── kb/
│   ├── terms.json         ingredient knowledge (see §4)
│   ├── qualifiers.json    phrases that resolve "varies" origins ("[Soy]", "plant source", "of vegetable origin")
│   ├── statement_items.json   allergen-statement words -> categories ("tree nuts", "nuts", "gluten", "cereals containing gluten")
│   ├── nutrients.json     printed nutrient labels -> keys, unit conversions
│   ├── names.json         English display names for categories / nutrients / bases (for explanations)
│   └── catalog.json       restriction catalog (must contain every key in shared/fixtures/catalog.json)
├── kb_loader.py           load + validate KB files with Pydantic models at import
├── normalize.py           text normalisation, INS/E code extraction, Indian-language name handling
├── matcher.py             ingredient text -> KB entries (with match type + score)
├── rules.py               master spec §9 per restriction -> RestrictionResult; profile overall
├── nutrition.py           per-100 / per-pack normalisation + consistency check
├── explain.py             explain_term
├── messages.py            renders English explanations from shared/messages.en.json + names.json
├── eval/
│   ├── dataset/README.md  how to photograph and label packets
│   ├── dataset/_template/truth.json
│   ├── eval_profiles.json fixed profiles used for expected verdicts
│   ├── run_eval.py        runs packets through the backend (or saved responses) and scores them
│   ├── metrics.py
│   └── reports/           report.json, report.md, metrics.json (copied to frontend by a human)
└── tests/
    ├── test_kb_valid.py
    ├── test_normalize.py
    ├── test_matcher.py
    ├── test_rules_table.py      one parametrised case per §9 row (+ precedence cases)
    ├── test_nutrition.py
    ├── test_fixture_scenario.py the fixture extraction + profiles must reproduce the fixture's verdict states
    └── test_catalog.py
```
Run from the **repo root**: `python -m pytest engine/tests`.

---

## 4. Knowledge base (`kb/terms.json`)

Each entry:
```json
{
  "id": "whey",
  "names": { "en": ["whey", "whey powder", "whey protein", "whey solids"], "hi": ["मट्ठा"], "te": [] },
  "ins": [],
  "categories": ["milk", "dairy"],
  "possible_categories": [],
  "origin": "animal",
  "notes": "Milk protein; always milk-derived.",
  "confidence": "high"
}
```
- `categories` = definite; `possible_categories` = only when origin is `varies` (e.g. INS 471 mono- and diglycerides: possible `animal_derived`; "natural flavours": possible `onion`, `garlic`, `animal_derived`, `dairy`).
- **Accuracy rule:** only encode facts you are confident are standard (food-additive references, FSSAI/Codex usage). When sources or community practice differ (e.g. whether dried ginger or turmeric is acceptable for every Jain), use `possible_categories` → the result becomes "Check this", never "Conflict". Never invent INS numbers. Put a `notes` line on every contested entry. Mark `confidence: "medium"` when unsure; the team will review those.

**Coverage targets (minimum):**
- **Allergens (all 15 categories)** with Indian names: groundnut/moongphali/singdana; maida, atta, sooji/rava, suji, semolina, durum, barley/jau, rye, oats (possible gluten); milk solids, milk powder, skimmed milk powder, whey, casein/caseinate, lactose, butter, ghee, cream, khoya/mawa, paneer, dahi/curd, malai, cheese, buttermilk; egg, albumin, egg lecithin, lysozyme (INS 1105); soy/soya, soy lecithin, soy protein; sesame/til/gingelly; mustard/rai/sarson; cashew/kaju, almond/badam, pistachio/pista, walnut/akhrot, hazelnut; fish, fish sauce; prawn/shrimp/jhinga, crab; sulphites (INS 220–228); celery; lupin; molluscs.
- **Diet:** meat/chicken/mutton/beef/pork/lard/tallow; gelatin (INS 441); carmine/cochineal (INS 120, `insect_derived`); shellac (INS 904, `insect_derived`); beeswax (INS 901); honey; bone phosphate (INS 542, `animal_derived`); animal rennet (definite) vs "rennet"/"enzymes" (varies); L-cysteine (INS 920, varies); INS 471/472a–f (varies); INS 627/631/635 (varies — can be animal or microbial); lactitol (INS 966, milk); onion/pyaz, garlic/lahsun (incl. powder, dehydrated, flakes, "onion & garlic powder"); root vegetables (potato/aloo, carrot/gajar, beetroot, radish/mooli, sweet potato, ginger/adrak — fresh ginger definite; "spices and condiments" → possible onion/garlic); alcohol (wine, rum, "alcohol-based flavouring").
- **Sugars:** sugar, cane sugar, brown sugar, jaggery/gur, khandsari, honey (also `honey`), invert sugar/invert syrup, glucose, liquid glucose, glucose syrup, dextrose, fructose, HFCS, corn syrup, maltodextrin, maltose, malt extract, date syrup/paste, sucrose → `added_sugar` (+ `sugar_alias` for the non-obvious names). Polyols: sorbitol 420, mannitol 421, isomalt 953, maltitol 965, lactitol 966 (also milk), xylitol 967, erythritol 968 → `polyol`. Sweeteners: acesulfame K 950, aspartame 951, cyclamate 952, saccharin 954, sucralose 955, neotame 961 → `artificial_sweetener`; steviol glycosides 960 → note "plant-derived, not counted as artificial" (no category).
- **Others:** palm oil/palmolein/palm fat/"edible vegetable oil (palm)"; caffeine, coffee, guarana; MSG/INS 621 → `added_msg`; common neutral items (salt, iodised salt, cocoa butter, cocoa solids, raising agents INS 500/503, citric acid INS 330, etc.) with empty categories so they count as "resolved" rather than unknown.
- Aim for ≥ 250 entries by the end of Phase 3. Hindi/Telugu names where commonly printed.

---

## 5. Matching (`normalize.py`, `matcher.py`)

Normalise: lowercase, Unicode NFKC, strip percentages and quantities, unify brackets, collapse spaces; extract INS/E codes from forms like `INS 322`, `E322`, `322(i)`, `500(ii)`, `INS 471, 472e` (one ingredient can carry several codes — "Emulsifiers (471, 472e)"); keep the parenthesised **qualifiers** text separately ("[Soy]", "(from sunflower)").

Match order for one ingredient (and recursively its sub-ingredients and any bracketed list inside it, e.g. "Chocolate (sugar, cocoa butter, milk solids)"):
1. INS code → entry (each code separately).
2. Exact name/alias after normalisation.
3. Whole-word alias contained in the text ("milk chocolate" → milk; "peanut butter" → peanut) — longest alias wins; avoid false hits ("coconut" must not hit "nut"; "butter" in "cocoa butter" / "peanut butter" must not hit dairy → keep explicit compound entries and a stop-list).
4. Fuzzy (rapidfuzz `token_sort_ratio` ≥ 92, aliases ≥ 5 chars only) to absorb OCR typos ("pea nuts", "whey pow der").
5. No match → `unresolved_terms`.
Qualifiers can turn `varies` into definite: "(INS 322 [Soy])" → soy definite; "INS 471 (vegetable origin)" → plant, no animal category.
Return per ingredient an `IngredientAnnotation` (`source: "kb"` / `"llm_interpretation"` / `"unresolved"`).

---

## 6. Rules (`rules.py`)

Implement master spec §9 literally. Specifics:
- Inputs: catalog categories for `restriction.key` (from your `kb/catalog.json`), severity, threshold. Unknown restriction key → result `unknown/undeterminable`, reason `UNKNOWN_NOT_ON_LABELS`, message `verdict.unknown.not_on_labels` (never crash).
- Skip `unreadable` ingredients for matching but they make the section count as not fully readable.
- Statement items → categories via `statement_items.json` ("nuts" alone → `tree_nut` definite + `peanut` possible; "cereals containing gluten" → `gluten`).
- **Veg mark** handling exactly as §9's note, including the "internally inconsistent label" note.
- **Thresholds:** compare at `threshold.basis`; convert per-serving ↔ per-100 using serving size when the requested basis is missing; skip suspect keys from the consistency check.
- `message_params` conventions (the frontend translates them): `category` = one category id or several joined by `|`; `nutrient` = nutrient key; `basis` = basis id (`per_100g`); `term`/`item` = label text verbatim; `value`/`limit` = numbers; `unit` = unit string. `explanation` = English rendering via `messages.py` with human names from `names.json`.
- Evidence and matches ordering per §9 (worst-state evidence first). Confidence rules per §9.
- `overall` = worst state. Also produce `UnknownItem`s: truncated ingredients, unreadable regions (copy `unreadable_regions` from sections), missing allergen statement (`unknown.no_allergen_statement`, only informative), unclear veg mark.

---

## 7. Nutrition (`nutrition.py`)

- Build `per_100` from `per_100g`/`per_100ml` values; if absent, derive from `per_serving` and serving size. `per_pack` from per-100 × pack size / 100, or per-serving × servings per pack.
- Conversions: kJ → kcal (÷ 4.184); salt g → sodium mg (× 400); mg ↔ g.
- **Consistency check:** computed kcal = 4·protein + 4·carbohydrate + 9·fat (+ 2.4·polyols if a polyol row exists, subtract fibre from carbohydrate only if the label clearly lists carbohydrate including fibre — default: don't). Deviation ≤ 15 % → `consistent`; otherwise `inconsistent`. Identify `suspect_keys`: try single-field corrections (×10, ÷10, digit swaps 0↔8, 1↔7, 5↔6, missing decimal point) and mark the field whose correction brings deviation within 5 %; if none, mark energy + all macros. Missing any of energy/protein/carbohydrate/fat → `insufficient_data`.
- Extra sanity checks feeding `suspect_keys`: sugars ≤ carbohydrate; saturated ≤ total fat; added sugars ≤ total sugars; per-serving vs per-100 ratio consistent with serving size (± 10 %).
- `notes`: `nutrition.serving_small` when servings_per_pack ≥ 2.

---

## 8. Explain (`explain.py`)

`explain_term(term, lang)` → KB lookup via the matcher → `ExplainResponse` with display name (localised name if the KB has one for `lang`), short English description from `notes`, origin, categories, caution for contested entries. Unknown → `None` (the backend asks the LLM).

---

## 9. Evaluation harness (`eval/`)

Humans photograph 10–15 real packets during Phase 1–2 (see `eval/dataset/README.md` you write): for each packet a folder `eval/dataset/<id>/` with `img_0.jpg` (and more panels if needed) at ≤ 2000 px, plus a `truth.json`:
```json
{
  "product": "…",
  "ingredients": ["Sugar", "Peanuts", "…"],
  "ingredients_complete_in_photos": true,
  "allergen_statements": { "contains": ["peanut", "milk"], "may_contain": ["tree nuts"] },
  "veg_mark": "veg",
  "nutrition_per_100": { "energy_kcal": 520, "total_sugars_g": 38 },
  "expected": [ { "eval_profile": "peanut_allergy", "state": "conflict" } ]
}
```
`eval_profiles.json` defines ~8 standard profiles (peanut allergy, milk allergy, gluten, vegetarian, vegan, Jain, diabetic sugar limit, low sodium).

`run_eval.py --backend http://localhost:8000` (or `--responses dir` for saved JSON) scores:
- ingredient precision / recall (fuzzy ≥ 85),
- nutrient value accuracy (within ± 2 % or printed rounding),
- allergen statement accuracy, veg mark accuracy,
- verdict accuracy with a 4×4 confusion matrix,
- **dangerous-miss rate** = expected `conflict` predicted `not_listed` (the headline number; target 0),
- evidence `verified` rate, unknown rate, average latency.
Writes `eval/reports/report.json`, `report.md` (readable table) and `metrics.json` (small, for the frontend About page).

Keep dataset images small (≤ 400 KB each) and commit them only if the team agrees; otherwise keep them local and commit truth files + reports.

---

## 10. Testing
- `test_rules_table.py`: build tiny `LabelExtraction`s in code for every §9 row and the precedence rules (conflict beats unknown; preference + may contain; green mark + egg ingredient → conflict with inconsistency note; truncated list + no match → not_detected; missing section → undeterminable).
- `test_fixture_scenario.py`: load `shared/fixtures/scan_result.json`, run `evaluate(extraction, profiles.json)`, assert each restriction's `state`, `unknown_kind` and `reason_code` equal the fixture's. This is the integration test that guarantees the frontend's demo matches reality.
- `test_matcher.py`: ≥ 60 cases including tricky ones (coconut ≠ tree nut; cocoa butter ≠ dairy; peanut butter = peanut; "milk chocolate" = milk; "edible vegetable oil (palm)" = palm oil; "Emulsifier (INS 322 [Soy])" = soy; OCR typos).
- `test_kb_valid.py`: every category is in `CATEGORIES`; no duplicate aliases across entries unless deliberate; every catalog key from the shared fixture exists.

## 11. Done criteria
- `python -m pytest engine/tests` green (aim ≥ 120 tests by the end).
- `test_fixture_scenario.py` passes.
- KB ≥ 250 entries; contested entries noted.
- Eval runs on ≥ 10 real packets after Merge 1 and produces the three report files; dangerous-miss rate reported honestly.

## 12. Do not
- Do not edit anything outside `engine/` (not `shared/`, not `backend/`). Contract change needed → write it in `engine/NOTES_FOR_OTHERS.md` and tell the team.
- No network calls, no LLM calls, no global mutable state, no randomness.
- Never output "safe". Never let an LLM interpretation produce `conflict`.
