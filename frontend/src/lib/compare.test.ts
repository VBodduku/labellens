import { describe, expect, it } from "vitest";
import { fixtureProfiles, fixtureScanResult } from "../api/fixtures";
import type { ScanResult } from "../shared/contract";
import { differences, familyComparison, nutritionComparison } from "./compare";

/** Product A is the demo chocolate bar: 40 g servings, peanuts, sodium unreadable. */
const a: ScanResult = fixtureScanResult;

/**
 * Product B: a different packet with 25 g servings that prints only per-serving values, so its per-100 values
 * are the engine's calculation; no peanut ingredient, a fully read list.
 */
function productB(edit: (b: ScanResult) => void = () => undefined): ScanResult {
  const b = structuredClone(fixtureScanResult);
  b.scan_id = "scan_b";
  b.extraction.product_name = "Masala Namkeen";
  const nutrition = b.extraction.nutrition!;
  nutrition.serving_size = 25;
  for (const row of nutrition.rows) row.values = row.values.filter((value) => value.basis === "per_serving");
  b.nutrition_analysis!.per_100 = { energy_kcal: 530, protein_g: 9, total_sugars_g: 4, total_fat_g: 30, sodium_mg: 650, trans_fat_g: 0.2 };
  b.extraction.ingredients = b.extraction.ingredients.filter((ingredient) => ingredient.id !== "ing_1");
  b.annotations = b.annotations.filter((annotation) => annotation.ingredient_id !== "ing_1");
  edit(b);
  return b;
}

describe("nutritionComparison", () => {
  it("lines products up per 100 g even when B prints only per-serving values", () => {
    const comparison = nutritionComparison(a, productB());
    expect(comparison.comparable).toBe(true);
    const sugars = comparison.rows.find((row) => row.key === "total_sugars_g");
    expect(sugars).toMatchObject({ a: { amount: 38, status: "ok", derived: false }, b: { amount: 4, status: "ok", derived: true } });
    expect(sugars?.difference?.lower).toBe("b");
    expect(sugars?.difference?.pct).toBeCloseTo(89.5, 1);
  });

  it("never compares a value that couldn't be read", () => {
    const sodium = nutritionComparison(a, productB()).rows.find((row) => row.key === "sodium_mg");
    expect(sodium).toMatchObject({ a: { amount: null, status: "unreadable" }, b: { amount: 650, status: "ok" }, difference: null });
  });

  it("never compares a value the calorie check says may be misread", () => {
    const b = productB((result) => {
      result.nutrition_analysis!.consistency.suspect_keys = ["total_sugars_g"];
    });
    const sugars = nutritionComparison(a, b).rows.find((row) => row.key === "total_sugars_g");
    expect(sugars).toMatchObject({ b: { status: "suspect" }, difference: null });
  });

  it("does not compare per 100 g with per 100 ml", () => {
    const b = productB((result) => {
      result.nutrition_analysis!.per_100_unit = "ml";
    });
    const comparison = nutritionComparison(a, b);
    expect(comparison).toMatchObject({ comparable: false, unitA: "g", unitB: "ml" });
    expect(comparison.rows.every((row) => row.difference === null)).toBe(true);
  });

  it("ignores small or tiny differences (0.1 g vs 0.2 g trans fat; 520 vs 530 kcal)", () => {
    const rows = nutritionComparison(a, productB()).rows;
    expect(rows.find((row) => row.key === "trans_fat_g")?.difference).toBeNull();
    expect(rows.find((row) => row.key === "energy_kcal")?.difference).toBeNull();
  });
});

describe("differences", () => {
  it("says B doesn't list peanuts only when B's list was read completely", () => {
    const found = differences(a, productB(), null).find((item) => item.kind === "category" && item.category === "peanut");
    expect(found).toEqual({ kind: "category", category: "peanut", product: "a", terms: ["Peanuts (22%)"], other: "absent" });
  });

  it("says 'not in the readable part' for an incomplete list and 'unreadable' for a missing one", () => {
    const partial = productB((result) => {
      result.extraction.ingredients_section = { ...result.extraction.ingredients_section, presence: "partial", complete: false };
    });
    const missing = productB((result) => {
      result.extraction.ingredients_section = { ...result.extraction.ingredients_section, presence: "not_found", complete: false };
    });
    const peanut = (b: ScanResult) => differences(a, b, null).find((item) => item.kind === "category" && item.category === "peanut");
    expect(peanut(partial)).toMatchObject({ other: "not_in_readable_part" });
    expect(peanut(missing)).toMatchObject({ other: "list_unreadable" });
  });

  it("keeps to the family's categories when given, and never counts an AI interpretation", () => {
    expect(differences(a, productB(), new Set(["milk"])).filter((item) => item.kind === "category")).toEqual([]);
    const interpreted = structuredClone(fixtureScanResult);
    interpreted.annotations = interpreted.annotations.map((annotation) =>
      annotation.ingredient_id === "ing_1" ? { ...annotation, source: "llm_interpretation" as const } : annotation,
    );
    expect(differences(interpreted, productB(), null).some((item) => item.kind === "category")).toBe(false);
  });

  it("lists large per-100 gaps after the ingredient differences, largest first", () => {
    const nutrients = differences(a, productB(), null).filter((item) => item.kind === "nutrient");
    expect(nutrients.map((item) => item.key)).toEqual(["total_sugars_g"]);
  });
});

describe("familyComparison", () => {
  it("pairs each person's verdicts for A and B, restriction by restriction", () => {
    const b = productB((result) => {
      result.reports = result.reports.filter((report) => report.profile_id !== "p_lakshmi");
    });
    const rows = familyComparison(a, b, fixtureProfiles);
    expect(rows.map((row) => row.profile.profile_id)).toEqual(fixtureProfiles.map((profile) => profile.profile_id));
    const aarav = rows.find((row) => row.profile.profile_id === "p_aarav");
    expect(aarav?.a?.overall).toBe("conflict");
    expect(aarav?.restrictions[0]?.a?.state).toBe("conflict");
    const lakshmi = rows.find((row) => row.profile.profile_id === "p_lakshmi");
    expect(lakshmi?.b).toBeNull();
    expect(lakshmi?.restrictions.every((pair) => pair.b === null)).toBe(true);
  });
});
