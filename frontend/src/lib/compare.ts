import {
  NUTRIENT_KEYS,
  type Ingredient,
  type Profile,
  type ProfileReport,
  type Restriction,
  type RestrictionResult,
  type ScanResult,
} from "../shared/contract";

/** Two scanned products side by side: "a" was scanned first, "b" second. */
export type Side = "a" | "b";

export interface RestrictionPair {
  restriction: Restriction;
  a: RestrictionResult | null;
  b: RestrictionResult | null;
}

export interface FamilyRow {
  profile: Profile;
  a: ProfileReport | null;
  b: ProfileReport | null;
  restrictions: RestrictionPair[];
}

/** Each family member's engine verdicts for both products, restriction by restriction. */
export function familyComparison(a: ScanResult, b: ScanResult, profiles: readonly Profile[]): FamilyRow[] {
  const report = (result: ScanResult, id: string) => result.reports.find((item) => item.profile_id === id) ?? null;
  const resultOf = (item: ProfileReport | null, id: string) => item?.results.find((r) => r.restriction_id === id) ?? null;
  return profiles.map((profile) => {
    const reportA = report(a, profile.profile_id);
    const reportB = report(b, profile.profile_id);
    return {
      profile,
      a: reportA,
      b: reportB,
      restrictions: profile.restrictions.map((restriction) => ({
        restriction,
        a: resultOf(reportA, restriction.id),
        b: resultOf(reportB, restriction.id),
      })),
    };
  });
}

/** ok: a per-100 value the engine accepted; suspect: the calorie check says it may be misread. */
export type ValueStatus = "ok" | "unreadable" | "suspect" | "not_printed";

export interface NutrientSide {
  amount: number | null;
  status: ValueStatus;
  /** Worked out from a per-serving or whole-pack value, not printed per 100. */
  derived: boolean;
}

export interface NutrientComparison {
  key: string;
  unit: string;
  a: NutrientSide;
  b: NutrientSide;
  /** The side with less of the nutrient and by how much, when the difference is large enough to point out. */
  difference: { lower: Side; pct: number } | null;
}

export interface NutritionComparison {
  /** Both labels give values per 100 of the same unit (g or ml); otherwise no differences are worked out. */
  comparable: boolean;
  unitA: "g" | "ml";
  unitB: "g" | "ml";
  rows: NutrientComparison[];
}

/** A difference is pointed out from this share of the larger value, and only above an absolute floor per unit. */
export const MIN_DIFFERENCE_PCT = 20;
const FLOOR: Record<string, number> = { kcal: 10, g: 0.5, mg: 20 };

export function nutrientUnit(key: string): string {
  if (key.endsWith("_kcal")) return "kcal";
  if (key.endsWith("_mg")) return "mg";
  return "g";
}

function per100Unit(result: ScanResult): "g" | "ml" {
  return result.nutrition_analysis?.per_100_unit ?? "g";
}

function nutrientSide(result: ScanResult, key: string): NutrientSide {
  const rows = (result.extraction.nutrition?.rows ?? []).filter((row) => row.key === key);
  const analysis = result.nutrition_analysis;
  const amount = analysis?.per_100[key];
  const printedPer100 = rows.some((row) =>
    row.values.some((value) => (value.basis === "per_100g" || value.basis === "per_100ml") && value.amount !== null && value.amount !== undefined),
  );
  if (analysis?.consistency.suspect_keys.includes(key)) return { amount: amount ?? null, status: "suspect", derived: false };
  if (amount !== undefined) return { amount, status: "ok", derived: !printedPer100 };
  return { amount: null, status: rows.length > 0 ? "unreadable" : "not_printed", derived: false };
}

function difference(key: string, a: NutrientSide, b: NutrientSide): NutrientComparison["difference"] {
  if (a.status !== "ok" || b.status !== "ok" || a.amount === null || b.amount === null) return null;
  const higher = Math.max(a.amount, b.amount);
  const gap = Math.abs(a.amount - b.amount);
  if (higher <= 0 || gap < (FLOOR[nutrientUnit(key)] ?? 0)) return null;
  const pct = (gap / higher) * 100;
  return pct >= MIN_DIFFERENCE_PCT ? { lower: a.amount < b.amount ? "a" : "b", pct } : null;
}

/** Per-100 values side by side (the engine's per_100, so labels with different serving sizes line up). */
export function nutritionComparison(a: ScanResult, b: ScanResult): NutritionComparison {
  const comparable = per100Unit(a) === per100Unit(b);
  const rows = NUTRIENT_KEYS.filter((key) => key !== "other")
    .map((key) => {
      const sideA = nutrientSide(a, key);
      const sideB = nutrientSide(b, key);
      return { key, unit: nutrientUnit(key), a: sideA, b: sideB, difference: comparable ? difference(key, sideA, sideB) : null };
    })
    .filter((row) => row.a.status !== "not_printed" || row.b.status !== "not_printed");
  return { comparable, unitA: per100Unit(a), unitB: per100Unit(b), rows };
}

/** What the other product's ingredient list lets us say about a category one product lists. */
export type OtherSide = "absent" | "not_in_readable_part" | "list_unreadable";

export type Difference =
  | { kind: "category"; category: string; product: Side; terms: string[]; other: OtherSide }
  | { kind: "nutrient"; key: string; lower: Side; pct: number };

function flatten(ingredients: readonly Ingredient[]): Ingredient[] {
  return ingredients.flatMap((ingredient) => [ingredient, ...flatten(ingredient.sub_ingredients)]);
}

/** Category -> ingredient names, from definite knowledge-base matches only (never an AI interpretation). */
function categoryTerms(result: ScanResult): Map<string, string[]> {
  const names = new Map(flatten(result.extraction.ingredients).map((ingredient) => [ingredient.id, ingredient.name]));
  const terms = new Map<string, string[]>();
  for (const annotation of result.annotations) {
    if (annotation.source !== "kb") continue;
    const name = names.get(annotation.ingredient_id);
    if (!name) continue;
    for (const category of annotation.categories) {
      const list = terms.get(category) ?? [];
      if (!list.includes(name)) terms.set(category, [...list, name]);
    }
  }
  return terms;
}

/** "Doesn't list" only when the whole list was read; otherwise say what can and can't be known. */
function otherSide(result: ScanResult): OtherSide {
  const section = result.extraction.ingredients_section;
  if (section.presence === "not_found") return "list_unreadable";
  return section.complete ? "absent" : "not_in_readable_part";
}

/**
 * The differences worth pointing out: ingredient categories one product lists and the other doesn't (limited to
 * `relevant` categories when given, e.g. what the family's restrictions care about), then large per-100 gaps.
 */
export function differences(a: ScanResult, b: ScanResult, relevant: ReadonlySet<string> | null): Difference[] {
  const terms: Record<Side, Map<string, string[]>> = { a: categoryTerms(a), b: categoryTerms(b) };
  const results: Record<Side, ScanResult> = { a, b };
  const categories: Difference[] = [];
  for (const [product, other] of [["a", "b"], ["b", "a"]] as const) {
    for (const [category, names] of terms[product]) {
      if (terms[other].has(category) || (relevant && !relevant.has(category))) continue;
      categories.push({ kind: "category", category, product, terms: names, other: otherSide(results[other]) });
    }
  }
  const nutrients: Difference[] = nutritionComparison(a, b)
    .rows.flatMap((row) => (row.difference ? [{ kind: "nutrient" as const, key: row.key, ...row.difference }] : []))
    .sort((x, y) => y.pct - x.pct);
  return [...categories, ...nutrients];
}
