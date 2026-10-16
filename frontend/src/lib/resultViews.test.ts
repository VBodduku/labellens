import { describe, expect, it } from "vitest";
import { fixtureScanResult } from "../api/fixtures";
import type { ScanResult } from "../shared/contract";
import { applyCorrections, makeCorrection } from "./corrections";
import { fitWithin } from "./imageProcessing";
import { hasServingValues, nutritionRows } from "./nutritionView";
import { changedVerdicts, verdictKey } from "./resultDiff";
import { profileSummary, templateSummary } from "./templateSummary";
import { sortByStateWorstFirst } from "./verdict";

const result = fixtureScanResult;

describe("fitWithin", () => {
  it("downsizes the long side to 2000 px and never upscales", () => {
    expect(fitWithin(4032, 3024)).toEqual({ width: 2000, height: 1500 });
    expect(fitWithin(3000, 4000)).toEqual({ width: 1500, height: 2000 });
    expect(fitWithin(1200, 900)).toEqual({ width: 1200, height: 900 });
  });
});

describe("nutritionRows", () => {
  it("shows the label's per-100 g values with editable field paths", () => {
    const rows = nutritionRows(result, "per_100");
    const sugars = rows.find((row) => row.key === "total_sugars_g");
    expect(sugars).toMatchObject({ amount: 38, unit: "g", readability: "clear" });
    expect(sugars?.fieldPath).toMatch(/^nutrition\.rows\[\d+\]\.values\[0\]\.amount$/);
  });

  it("marks the smudged sodium value as unreadable on every basis", () => {
    for (const view of ["per_100", "per_serving", "per_pack"] as const) {
      const sodium = nutritionRows(result, view).find((row) => row.key === "sodium_mg");
      expect(sodium?.amount, view).toBeNull();
      expect(sodium?.readability, view).toBe("unreadable");
    }
  });

  it("uses per-serving values from the label and derived whole-pack values (read-only)", () => {
    expect(hasServingValues(result)).toBe(true);
    expect(nutritionRows(result, "per_serving").find((row) => row.key === "energy_kcal")?.amount).toBe(208);
    const pack = nutritionRows(result, "per_pack").find((row) => row.key === "energy_kcal");
    expect(pack).toMatchObject({ amount: 624, fieldPath: null, edited: false });
  });

  it("flags user-corrected values as edited", () => {
    const sodiumRow = result.extraction.nutrition?.rows.findIndex((row) => row.key === "sodium_mg") ?? -1;
    const path = `nutrition.rows[${sodiumRow}].values[0].amount`;
    const corrected: ScanResult = {
      ...result,
      extraction: applyCorrections(result.extraction, [makeCorrection(result.extraction, path, 125)]),
    };
    const sodium = nutritionRows(corrected, "per_100").find((row) => row.key === "sodium_mg");
    expect(sodium).toMatchObject({ amount: 125, edited: true });
  });

  it("shows calculated per-100 values (read-only) when the label prints only per serving", () => {
    const servingOnly: ScanResult = structuredClone(result);
    for (const row of servingOnly.extraction.nutrition?.rows ?? []) row.values = row.values.filter((value) => value.basis !== "per_100g");
    const rows = nutritionRows(servingOnly, "per_100");
    expect(rows.find((row) => row.key === "energy_kcal")).toMatchObject({ amount: 520, derived: true, fieldPath: null });
    expect(rows.find((row) => row.key === "sodium_mg")).toMatchObject({ amount: null, derived: true });
    expect(nutritionRows(result, "per_100").find((row) => row.key === "energy_kcal")?.derived).toBe(false);
  });

  it("flags suspect rows from the consistency check", () => {
    const suspect: ScanResult = structuredClone(result);
    if (suspect.nutrition_analysis) suspect.nutrition_analysis.consistency.suspect_keys = ["total_fat_g"];
    expect(nutritionRows(suspect, "per_100").find((row) => row.key === "total_fat_g")?.suspect).toBe(true);
  });
});

describe("changedVerdicts", () => {
  it("lists only verdicts whose state changed", () => {
    const next: ScanResult = structuredClone(result);
    const sodium = next.reports[1]?.results.find((item) => item.restriction_id === "r_thatha_sodium");
    if (sodium) {
      sodium.state = "not_listed";
      sodium.unknown_kind = null;
    }
    expect(changedVerdicts(result, next)).toEqual([verdictKey("p_thatha", "r_thatha_sodium")]);
    expect(changedVerdicts(result, structuredClone(result))).toEqual([]);
    expect(changedVerdicts(null, result)).toEqual([]);
  });
});

describe("summaries", () => {
  const thatha = result.reports[1]!;

  it("uses the grounded summary when it is in the current language", () => {
    expect(profileSummary(thatha, "Thatha", "en")).toBe(thatha.summary);
  });

  it("falls back to a template built only from fixed messages", () => {
    expect(templateSummary(thatha, "Thatha", "en")).toBe(
      "Thatha — Conflicts with this profile. Total sugars is 38 g per 100 g, above your limit of 22.5 g.",
    );
    expect(profileSummary(thatha, "Thatha", "te")).not.toBe(thatha.summary);
  });
});

describe("report ordering", () => {
  it("puts the worst overall first and keeps ties stable", () => {
    const order = sortByStateWorstFirst(result.reports, (report) => report.overall).map((report) => report.profile_id);
    expect(order).toEqual(["p_aarav", "p_thatha", "p_lakshmi"]);
  });
});
