import { useTranslation } from "react-i18next";
import { VERDICT_ORDER, type VerdictState } from "../../shared/contract";
import { StateBadge } from "../verdict/StateBadge";
import { Reveal, SectionHeading } from "./Reveal";

const ACCENT: Record<VerdictState, string> = {
  conflict: "before:bg-conflict",
  possible: "before:bg-possible",
  unknown: "before:bg-unknown",
  not_listed: "before:bg-not-listed",
};

/** The four states, each with a tiny real example from the demo label. */
export function HonestySection() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="honesty-title" className="page-gutter mx-auto max-w-page py-20 lg:py-28">
      <SectionHeading
        id="honesty-title"
        eyebrow={t("landing.honesty.eyebrow")}
        title={t("landing.honesty.title")}
        body={t("landing.honesty.body")}
      />
      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:mt-14 lg:grid-cols-4">
        {VERDICT_ORDER.map((state, index) => (
          <Reveal
            key={state}
            delay={index * 0.06}
            className={`card relative flex flex-col gap-4 overflow-hidden p-6 before:absolute before:inset-x-0 before:top-0 before:h-[3px] ${ACCENT[state]}`}
          >
            <StateBadge state={state} size="lg" className="self-start" />
            <p className="text-sm leading-relaxed text-text">{t(`landing.honesty.${state}.example`)}</p>
            {state === "unknown" && (
              <div className="mt-auto flex flex-wrap gap-2 border-t border-line pt-4">
                <StateBadge state="unknown" unknownKind="not_detected" size="sm" />
                <StateBadge state="unknown" unknownKind="undeterminable" size="sm" />
              </div>
            )}
          </Reveal>
        ))}
      </div>
      <Reveal className="mt-6 max-w-3xl">
        <p className="text-sm leading-relaxed text-text-dim">{t("landing.honesty.unknownKinds")}</p>
      </Reveal>
    </section>
  );
}
