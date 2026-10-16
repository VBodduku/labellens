import { VERDICT_ORDER, type VerdictState } from "../shared/contract";

/**
 * What the About page may say about accuracy, parsed from public/metrics.json — a copy of the engine's
 * engine/eval/reports/metrics.json: `{ status, metrics, generated_at }`. The engine only publishes
 * `status: "ready"` for real photographed packets; synthetic test runs stay "pending" with null rates.
 */
export type MetricsView =
  | { kind: "pending" }
  | {
      kind: "real";
      packets: number;
      verdictAccuracy: number | null;
      dangerousMissRate: number | null;
      evidenceVerifiedRate: number | null;
      unknownRate: number | null;
      ingredientPrecision: number | null;
      ingredientRecall: number | null;
      averageLatencyS: number | null;
      confusion: Record<VerdictState, Record<VerdictState, number>> | null;
      limitations: string[];
    }
  | { kind: "invalid" };

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function confusionMatrix(value: unknown): Record<VerdictState, Record<VerdictState, number>> | null {
  if (typeof value !== "object" || value === null) return null;
  const table = value as Record<string, unknown>;
  const rows = {} as Record<VerdictState, Record<VerdictState, number>>;
  for (const expected of VERDICT_ORDER) {
    const row = table[expected];
    if (typeof row !== "object" || row === null) return null;
    rows[expected] = {} as Record<VerdictState, number>;
    for (const actual of VERDICT_ORDER) rows[expected][actual] = num((row as Record<string, unknown>)[actual]) ?? 0;
  }
  return rows;
}

export function parseMetrics(data: unknown): MetricsView {
  if (typeof data !== "object" || data === null) return { kind: "invalid" };
  const envelope = data as Record<string, unknown>;
  if (envelope.status === "pending") return { kind: "pending" };
  const record = envelope.metrics;
  if (envelope.status !== "ready" || typeof record !== "object" || record === null) return { kind: "invalid" };
  const metrics = record as Record<string, unknown>;
  const packets = num(metrics.packets);
  if (packets === null || packets === 0) return { kind: "invalid" };
  return {
    kind: "real",
    packets,
    verdictAccuracy: num(metrics.verdict_accuracy),
    dangerousMissRate: num(metrics.dangerous_miss_rate),
    evidenceVerifiedRate: num(metrics.evidence_verified_rate),
    unknownRate: num(metrics.unknown_rate),
    ingredientPrecision: num(metrics.ingredient_precision),
    ingredientRecall: num(metrics.ingredient_recall),
    averageLatencyS: num(metrics.avg_latency_s),
    confusion: confusionMatrix(metrics.confusion_matrix),
    limitations: Array.isArray(metrics.limitations) ? metrics.limitations.filter((item): item is string => typeof item === "string") : [],
  };
}
