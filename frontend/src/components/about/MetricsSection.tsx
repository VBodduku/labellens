import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { formatNumber } from "../../lib/format";
import { parseMetrics, type MetricsView } from "../../lib/metrics";
import { VERDICT_ORDER } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { StateBadge } from "../verdict/StateBadge";

const METRICS_TIMEOUT_MS = 10_000;

type MetricsState = { status: "loading" } | { status: "error" } | { status: "loaded"; view: MetricsView };

/** Reads public/metrics.json (a copy of engine/eval/reports/metrics.json). */
function useMetrics(): MetricsState {
  const [state, setState] = useState<MetricsState>({ status: "loading" });
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), METRICS_TIMEOUT_MS);
    fetch("/metrics.json", { signal: controller.signal, cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<unknown>) : Promise.reject(new Error(String(response.status)))))
      .then((data) => {
        if (active) setState({ status: "loaded", view: parseMetrics(data) });
      })
      .catch(() => {
        if (active) setState({ status: "error" });
      })
      .finally(() => clearTimeout(timer));
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, []);
  return state;
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <dt className="text-xs text-text-dim">{label}</dt>
      <dd className="mt-1 font-display text-2xl font-bold tabular-nums">{value}</dd>
    </div>
  );
}

/** Measured accuracy — only from real packets; synthetic test runs are described, never shown as accuracy. */
export function MetricsSection() {
  const { t } = useTranslation();
  const lang = useUiStore((store) => store.lang);
  const state = useMetrics();
  const percent = (value: number | null) => (value === null ? "—" : `${formatNumber(Math.round(value * 1000) / 10, lang)}%`);

  if (state.status === "loading") return <p className="text-text-dim">{t("common.loading")}</p>;
  if (state.status === "error" || state.view.kind === "invalid") return <p className="card p-5 text-text-dim">{t("about.metrics.error")}</p>;
  if (state.view.kind === "pending") return <p className="card p-5 text-text-dim">{t("about.metrics.pending")}</p>;

  const view = state.view;
  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile label={t("about.metrics.packets")} value={formatNumber(view.packets, lang)} />
        <Tile label={t("about.metrics.verdicts")} value={percent(view.verdictAccuracy)} />
        <Tile label={t("about.metrics.dangerous")} value={percent(view.dangerousMissRate)} />
        <Tile label={t("about.metrics.evidence")} value={percent(view.evidenceVerifiedRate)} />
        <Tile label={t("about.metrics.unknown")} value={percent(view.unknownRate)} />
        <Tile label={t("about.metrics.recall")} value={percent(view.ingredientRecall)} />
        {view.averageLatencyS !== null && (
          <Tile label={t("about.metrics.latency")} value={t("about.metrics.seconds", { value: formatNumber(view.averageLatencyS, lang) })} />
        )}
      </dl>

      {view.confusion && (
        <div className="card overflow-x-auto p-4">
          <table className="w-full text-sm">
            <caption className="mb-3 text-left font-semibold">{t("about.metrics.confusion")}</caption>
            <thead>
              <tr>
                <th scope="col" className="pb-2 text-left text-xs font-semibold text-text-dim">
                  {t("about.metrics.expected")} ↓ / {t("about.metrics.given")} →
                </th>
                {VERDICT_ORDER.map((state) => (
                  <th key={state} scope="col" className="px-1 pb-2">
                    <StateBadge state={state} size="sm" compact />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {VERDICT_ORDER.map((expected) => (
                <tr key={expected} className="border-t border-line">
                  <th scope="row" className="py-2 text-left">
                    <StateBadge state={expected} size="sm" />
                  </th>
                  {VERDICT_ORDER.map((actual) => (
                    <td key={actual} className={`py-2 text-center tabular-nums ${expected === actual ? "font-bold" : "text-text-dim"}`}>
                      {view.confusion?.[expected][actual] ?? 0}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {view.limitations.length > 0 && (
        <div>
          <h3 className="font-semibold">{t("about.metrics.limitations")}</h3>
          <ul lang="en" className="mt-2 list-disc space-y-1 pl-5 text-sm text-text-dim">
            {view.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
