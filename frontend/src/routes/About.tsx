import { useTranslation } from "react-i18next";
import { MetricsSection } from "../components/about/MetricsSection";
import { StateBadge } from "../components/verdict/StateBadge";
import { VERDICT_ORDER } from "../shared/contract";

const PIPELINE = ["capture", "read", "understand", "verify", "decide"] as const;
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
        <MetricsSection />
      </Section>
    </div>
  );
}
