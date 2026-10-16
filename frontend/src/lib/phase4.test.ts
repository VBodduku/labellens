import { describe, expect, it } from "vitest";
import { fixtureProfiles, fixtureScanResult } from "../api/fixtures";
import { unreadableScenario } from "../api/mockScenarios";
import { isIos } from "./installPrompt";
import { parseMetrics } from "./metrics";

describe("install prompt platform detection", () => {
  it("recognises iPhone, iPad (desktop-class UA) and not Android or desktop", () => {
    expect(isIos("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15", 5)).toBe(true);
    expect(isIos("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.5 Safari", 5)).toBe(true);
    expect(isIos("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.5 Safari", 0)).toBe(false);
    expect(isIos("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/131 Mobile", 5)).toBe(false);
  });
});

describe("metrics parser", () => {
  const real = {
    status: "ready",
    generated_at: "2026-10-16T12:30:00Z",
    metrics: {
      packets: 12,
      verdict_accuracy: 0.9,
      dangerous_miss_rate: 0,
      evidence_verified_rate: 0.95,
      unknown_rate: 0.2,
      ingredient_precision: 0.97,
      ingredient_recall: 0.93,
      nutrient_accuracy: 0.9,
      avg_latency_s: 6.4,
      confusion_matrix: {
        conflict: { conflict: 8, possible: 1, unknown: 0, not_listed: 0 },
        possible: { conflict: 0, possible: 3, unknown: 0, not_listed: 0 },
        unknown: { conflict: 0, possible: 0, unknown: 3, not_listed: 0 },
        not_listed: { conflict: 0, possible: 0, unknown: 0, not_listed: 1 },
      },
      limitations: ["Real packets photographed by the team.", 42],
    },
  };

  it("reads the engine's real-packet metrics, the confusion matrix and limitations", () => {
    const view = parseMetrics(real);
    expect(view.kind).toBe("real");
    if (view.kind !== "real") return;
    expect(view).toMatchObject({ packets: 12, verdictAccuracy: 0.9, dangerousMissRate: 0, averageLatencyS: 6.4 });
    expect(view.confusion?.conflict.possible).toBe(1);
    expect(view.limitations).toEqual(["Real packets photographed by the team."]);
  });

  it("shows nothing as accuracy until real packets are measured", () => {
    expect(parseMetrics({ status: "pending", metrics: { packets: 0, verdict_accuracy: null } })).toEqual({ kind: "pending" });
    expect(parseMetrics({ ...real, metrics: { ...real.metrics, packets: 0 } })).toEqual({ kind: "invalid" });
  });

  it("rejects malformed files", () => {
    expect(parseMetrics("nope")).toEqual({ kind: "invalid" });
    expect(parseMetrics({ status: "ready" })).toEqual({ kind: "invalid" });
    expect(parseMetrics({ dataset_kind: "real", real_packets: 3 })).toEqual({ kind: "invalid" });
  });
});

describe("unreadable mock scenario", () => {
  it("turns every verdict into an honest unknown, OCR-only, with incomplete sections", () => {
    const result = unreadableScenario(fixtureScanResult, fixtureProfiles);
    expect(result.extraction.meta.provider).toBe("ocr_only");
    expect(result.extraction.ingredients_section.complete).toBe(false);
    expect(result.reports.every((report) => report.overall === "unknown")).toBe(true);
    const thatha = result.reports.find((report) => report.profile_id === "p_thatha");
    expect(thatha?.results.find((item) => item.restriction_id === "r_thatha_sugar")).toMatchObject({
      unknown_kind: "undeterminable",
      message_key: "verdict.unknown.nutrient_missing",
      message_params: { nutrient: "total_sugars_g" },
    });
    const aarav = result.reports.find((report) => report.profile_id === "p_aarav");
    expect(aarav?.results[0]).toMatchObject({ unknown_kind: "not_detected", message_params: { category: "peanut" } });
    expect(result.unknowns.length).toBeGreaterThan(fixtureScanResult.unknowns.length);
    expect(fixtureScanResult.extraction.meta.provider).toBe("fixture");
  });

  it("gives profiles created in the app (not in the fixture) an unknown card for every restriction", () => {
    const mine = { ...fixtureProfiles[0]!, profile_id: "p_new", name: "Meera" };
    const result = unreadableScenario(fixtureScanResult, [mine]);
    expect(result.reports).toHaveLength(1);
    expect(result.reports[0]).toMatchObject({ profile_id: "p_new", overall: "unknown" });
    expect(result.reports[0]?.results).toHaveLength(mine.restrictions.length);
  });
});
