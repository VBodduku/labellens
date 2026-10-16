import { CATEGORIES, type Profile, type ScanResult } from "../shared/contract";

/** Restriction key → category ids for an "unreadable" message (allergen keys are their own category). */
function categoriesFor(key: string): string {
  if ((CATEGORIES as readonly string[]).includes(key)) return key;
  if (key === "jain" || key === "no_onion_garlic") return "onion|garlic|root_vegetable";
  if (key === "vegetarian" || key === "eggetarian" || key === "vegan") return "meat|egg_derived|gelatin";
  return "";
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
  copy.reports = copy.reports.map((report) => {
    const profile = profiles.find((candidate) => candidate.profile_id === report.profile_id);
    return {
      ...report,
      overall: "unknown",
      summary: null,
      summary_lang: null,
      results: report.results.map((item) => {
        const restriction = profile?.restrictions.find((candidate) => candidate.id === item.restriction_id);
        const nutrient = restriction?.threshold?.nutrient;
        const params: Record<string, string> = nutrient ? { nutrient } : { category: categoriesFor(restriction?.key ?? "") };
        return {
          ...item,
          state: "unknown",
          unknown_kind: nutrient ? "undeterminable" : "not_detected",
          reason_code: nutrient ? "UNKNOWN_NUTRIENT_MISSING" : "UNKNOWN_UNREADABLE",
          message_key: nutrient ? "verdict.unknown.nutrient_missing" : "verdict.unknown.unreadable",
          message_params: params,
          evidence: [],
          matches: [],
          confidence: 0.4,
        };
      }),
    };
  });
  copy.unknowns = [
    ...copy.unknowns,
    { section: "ingredients", message_key: "unknown.ingredients_truncated", detail: null, region: null },
    { section: "veg_mark", message_key: "unknown.veg_mark_unclear", detail: null, region: null },
    { section: "allergens", message_key: "unknown.no_allergen_statement", detail: null, region: null },
  ];
  return copy;
}
