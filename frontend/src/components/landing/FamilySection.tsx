import { useTranslation } from "react-i18next";
import { fixtureProfiles, fixtureScanResult } from "../../api/fixtures";
import { sortWorstFirst } from "../../lib/verdict";
import { Message } from "../ui/Message";
import { StateBadge } from "../verdict/StateBadge";
import { Reveal, SectionHeading } from "./Reveal";

const FAMILY = fixtureProfiles.flatMap((profile) => {
  const report = fixtureScanResult.reports.find((candidate) => candidate.profile_id === profile.profile_id);
  const worst = report ? sortWorstFirst(report.results)[0] : undefined;
  return report && worst ? [{ profile, report, worst }] : [];
});

/** One packet, one card per person — taken straight from the demo scan. */
export function FamilySection() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="family-title" className="border-t border-line bg-surface py-20 lg:py-28">
      <div className="page-gutter mx-auto grid max-w-page gap-10 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-center lg:gap-16">
        <SectionHeading
          id="family-title"
          eyebrow={t("landing.family.eyebrow")}
          title={t("landing.family.title")}
          body={t("landing.family.body")}
        />
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-text-dim">{t("landing.family.example")}</p>
          <ul className="space-y-3">
            {FAMILY.map(({ profile, report, worst }, index) => (
              <li key={profile.profile_id}>
                <Reveal delay={index * 0.08} className="card flex gap-4 p-4 sm:p-5">
                  <span
                    aria-hidden="true"
                    className="flex size-11 shrink-0 items-center justify-center rounded-full text-base font-bold text-[#0b0d12]"
                    style={{ background: profile.color ?? "var(--beam)" }}
                  >
                    {profile.name.slice(0, 1)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="text-base font-bold">{profile.name}</h3>
                      <StateBadge state={report.overall} unknownKind={worst.unknown_kind} />
                    </div>
                    <p className="mt-1 text-xs text-text-dim">{profile.restrictions.map((restriction) => restriction.label).join(" · ")}</p>
                    <p className="mt-2.5 text-sm leading-relaxed">
                      <Message messageKey={worst.message_key} params={worst.message_params} />
                    </p>
                  </div>
                </Reveal>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
