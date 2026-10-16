import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { StateBadge } from "../components/verdict/StateBadge";
import { VERDICT_ORDER } from "../shared/contract";

const PIPELINE = ["capture", "read", "understand", "verify", "decide"] as const;
const METRICS_TIMEOUT_MS = 10_000;

type Metrics =
  | { status: "loading" }
  | { status: "pending" }
  | { status: "error" }
  | { status: "ready"; values: [string, number][] };

/** Reads public/metrics.json (Part 3 provides the real numbers near the end; "pending" until then). */
function useMetrics(): Metrics {
  const [metrics, setMetrics] = useState<Metrics>({ status: "loading" });
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), METRICS_TIMEOUT_MS);
    fetch("/metrics.json", { signal: controller.signal, cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<unknown>) : Promise.reject(new Error(String(response.status)))))
      .then((data) => {
        if (!active) return;
        const record = typeof data === "object" && data !== null ? (data as Record<string, unknown>) : {};
        if (record.status !== "ready") {
          setMetrics({ status: "pending" });
          return;
        }
        const source = typeof record.metrics === "object" && record.metrics !== null ? (record.metrics as Record<string, unknown>) : {};
        const values = Object.entries(source).filter((entry): entry is [string, number] => typeof entry[1] === "number");
        setMetrics(values.length > 0 ? { status: "ready", values } : { status: "pending" });
      })
      .catch(() => {
        if (active) setMetrics({ status: "error" });
      })
      .finally(() => clearTimeout(timer));
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, []);
  return metrics;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line py-8">
      <h2 className="text-2xl font-bold">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function About() {
  const { t } = useTranslation();
  const metrics = useMetrics();
  return (
    <div className="page-gutter mx-auto max-w-3xl py-8 lg:py-12">
      <h1 className="text-3xl font-bold sm:text-4xl">{t("about.title")}</h1>
      <p className="mt-4 pb-8 text-lg leading-relaxed text-text-dim">{t("about.intro")}</p>

      <Section title={t("about.pipeline.title")}>
        <ol className="space-y-4">
          {PIPELINE.map((step, index) => (
            <li key={step} className="flex gap-4">
              <span className="evidence-text flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs text-beam">
                {index + 1}
              </span>
              <div>
                <h3 className="font-bold">{t(`landing.how.${step}.title`)}</h3>
                <p className="mt-1 text-sm leading-relaxed text-text-dim">{t(`landing.how.${step}.body`)}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section title={t("about.states.title")}>
        <ul className="space-y-3">
          {VERDICT_ORDER.map((state) => (
            <li key={state} className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <StateBadge state={state} className="self-start sm:self-center" />
              <p className="text-sm leading-relaxed">{t(`landing.honesty.${state}.example`)}</p>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm leading-relaxed text-text-dim">{t("landing.honesty.unknownKinds")}</p>
      </Section>

      <Section title={t("about.never.title")}>
        <p className="leading-relaxed text-text-dim">{t("about.never.body")}</p>
      </Section>

      <Section title={t("about.privacy.title")}>
        <p className="leading-relaxed text-text-dim">{t("about.privacy.body")}</p>
      </Section>

      <Section title={t("about.limits.title")}>
        <p className="leading-relaxed text-text-dim">{t("about.limits.body")}</p>
      </Section>

      <Section title={t("about.metrics.title")}>
        {metrics.status === "loading" && <p className="text-text-dim">{t("common.loading")}</p>}
        {metrics.status === "pending" && <p className="card p-5 text-text-dim">{t("about.metrics.pending")}</p>}
        {metrics.status === "error" && <p className="card p-5 text-text-dim">{t("about.metrics.error")}</p>}
        {metrics.status === "ready" && (
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {metrics.values.map(([name, value]) => (
              <div key={name} className="card p-4">
                <dt className="text-xs text-text-dim">{name.replace(/_/g, " ")}</dt>
                <dd className="mt-1 font-display text-2xl font-bold">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </Section>
    </div>
  );
}
