import { describe, expect, it } from "vitest";
import { fixtureScanResult } from "../api/fixtures";
import type { NutritionAnalysis } from "../shared/contract";
import { proteinRatio, ratioBand, scalePosition } from "./proteinRatio";

function analysis(per100: Record<string, number>, suspect: string[] = []): NutritionAnalysis {
  return {
    per_100: per100,
    per_100_unit: "g",
    per_pack: {},
    servings_per_pack: null,
    consistency: { status: "consistent", suspect_keys: suspect, message_key: "nutrition.consistency.ok" },
    notes: [],
  };
}

describe("calories-to-protein bands", () => {
  it.each([
    [5, "excellent"],
    [10, "excellent"],
    [10.1, "veryGood"],
    [15, "veryGood"],
    [15.1, "good"],
    [20, "good"],
    [20.1, "moderate"],
    [30, "moderate"],
    [30.1, "poor"],
    [50, "poor"],
    [50.1, "veryPoor"],
    [400, "veryPoor"],
  ])("%s kcal per g protein is %s", (ratio, band) => {
    expect(ratioBand(ratio).band).toBe(band);
  });

  it("places less protein on the left and more on the right, one equal segment per band", () => {
    expect(scalePosition(200)).toBe(0);
    expect(scalePosition(50)).toBeCloseTo(100 / 6);
    expect(scalePosition(20)).toBeCloseTo(50);
    expect(scalePosition(10)).toBeCloseTo((500 / 6));
    expect(scalePosition(2)).toBe(100);
    expect(scalePosition(12)).toBeGreaterThan(scalePosition(18));
  });
});

describe("proteinRatio", () => {
  it("divides per-100 calories by per-100 protein", () => {
    const ratio = proteinRatio(analysis({ energy_kcal: 165, protein_g: 31 }));
    expect(ratio).toMatchObject({ kind: "ratio", band: "excellent" });
    expect(ratio.kind === "ratio" && ratio.kcalPerGram).toBeCloseTo(5.32, 2);
  });

  it("rates the demo chocolate bar very poor", () => {
    expect(proteinRatio(fixtureScanResult.nutrition_analysis)).toMatchObject({ kind: "ratio", band: "veryPoor" });
  });

  it("never rates a guess when a value is missing or possibly misread", () => {
    expect(proteinRatio(null)).toEqual({ kind: "unavailable", reason: "missing" });
    expect(proteinRatio(analysis({ energy_kcal: 400 }))).toEqual({ kind: "unavailable", reason: "missing" });
    expect(proteinRatio(analysis({ energy_kcal: 400, protein_g: 8 }, ["protein_g"]))).toEqual({ kind: "unavailable", reason: "suspect" });
    expect(proteinRatio(analysis({ energy_kcal: 400, protein_g: 8 }, ["energy_kcal"]))).toEqual({ kind: "unavailable", reason: "suspect" });
  });

  it("calls zero protein 'no protein' (ratio undefined) and needs some calories", () => {
    expect(proteinRatio(analysis({ energy_kcal: 380, protein_g: 0 }))).toEqual({ kind: "no_protein", energy: 380 });
    expect(proteinRatio(analysis({ energy_kcal: 0, protein_g: 0 }))).toEqual({ kind: "unavailable", reason: "no_energy" });
  });
});
