import { CATEGORIES, type Profile, type Restriction, type RestrictionResult, type ScanResult } from "../shared/contract";

/** Restriction key → category ids for an "unreadable" message (allergen keys are their own category). */
function categoriesFor(key: string): string {
  if ((CATEGORIES as readonly string[]).includes(key)) return key;
  if (key === "jain" || key === "no_onion_garlic") return "onion|garlic|root_vegetable";
  if (key === "vegetarian" || key === "eggetarian" || key === "vegan") return "meat|egg_derived|gelatin";
  return "";
}

function unknownResult(restriction: Restriction): RestrictionResult {
  const nutrient = restriction.threshold?.nutrient;
  return {
    restriction_id: restriction.id,
    state: "unknown",
    unknown_kind: nutrient ? "undeterminable" : "not_detected",
    reason_code: nutrient ? "UNKNOWN_NUTRIENT_MISSING" : "UNKNOWN_UNREADABLE",
    message_key: nutrient ? "verdict.unknown.nutrient_missing" : "verdict.unknown.unreadable",
    message_params: nutrient ? { nutrient } : { category: categoriesFor(restriction.key) },
    explanation: "The label could not be read well enough to check this.",
    evidence: [],
    matches: [],
    confidence: 0.4,
  };
}

/**
 * Dev-only `?mockScenario=unreadable`: the fixture as if the photo were badly lit and the AI reader down —
 * OCR-only, every section incomplete, every verdict unknown. Exercises the unknown-heavy result UI.
 */
export function unreadableScenario(result: ScanResult, profiles: Profile[]): ScanResult {
  const copy = structuredClone(result);
  const extraction = copy.extraction;
  extraction.product_name = null;
  extraction.meta = { ...extraction.meta, provider: "ocr_only", model: "rapidocr", retries: [] };
  extraction.ingredients = extraction.ingredients.map((ingredient) => ({ ...ingredient, readability: "partial" }));
  for (const section of [extraction.ingredients_section, extraction.nutrition_section, extraction.allergen_section]) {
    section.presence = "partial";
    section.complete = false;
    section.issues = ["ocr_only"];
  }
  extraction.veg_mark = { value: "unclear", evidence: null };
  copy.annotations = copy.annotations.map((annotation) => ({ ...annotation, source: "unresolved" }));
  // Built from the profiles sent (not the fixture's reports), so families created in the app get cards too.
  copy.reports = profiles.map((profile) => ({
    profile_id: profile.profile_id,
    overall: "unknown",
    summary: null,
    summary_lang: null,
    results: profile.restrictions.map((restriction) => unknownResult(restriction)),
  }));
  copy.unknowns = [
    ...copy.unknowns,
    { section: "ingredients", message_key: "unknown.ingredients_truncated", detail: null, region: null },
    { section: "veg_mark", message_key: "unknown.veg_mark_unclear", detail: null, region: null },
    { section: "allergens", message_key: "unknown.no_allergen_statement", detail: null, region: null },
  ];
  return copy;
}
