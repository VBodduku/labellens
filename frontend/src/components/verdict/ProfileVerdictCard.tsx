import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { restrictionLabel } from "../../lib/restrictionLabel";
import { verdictKey } from "../../lib/resultDiff";
import { speechScript } from "../../lib/speechScript";
import { profileSummary } from "../../lib/templateSummary";
import { sortWorstFirst } from "../../lib/verdict";
import type { Profile, ProfileReport } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { ReadAloudButton } from "../speech/ReadAloudButton";
import { ResultCard } from "./ResultCard";
import { StateBadge } from "./StateBadge";

interface ProfileVerdictCardProps {
  report: ProfileReport;
  profile: Profile | undefined;
  changed: string[];
}

/**
 * One family member's verdict: overall headline, the grounded summary (or a template summary built from
 * fixed messages when it isn't in the current language), then every restriction worst-first.
 */
export function ProfileVerdictCard({ report, profile, changed }: ProfileVerdictCardProps) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const results = sortWorstFirst(report.results);
  const worst = results[0];
  const name = profile?.name ?? report.profile_id;
  const restrictionName = (restrictionId: string) => {
    const restriction = profile?.restrictions.find((candidate) => candidate.id === restrictionId);
    return restriction ? restrictionLabel(restriction.key, restriction.label, lang) : restrictionId;
  };

  return (
    <article className="card overflow-hidden" aria-labelledby={`verdict-${report.profile_id}`}>
      <header className="flex items-start gap-3 border-b border-line p-4 sm:p-5">
        <span
          aria-hidden="true"
          className="flex size-11 shrink-0 items-center justify-center rounded-full font-bold text-[#0b0d12]"
          style={{ background: profile?.color ?? "var(--beam)" }}
        >
          {name.slice(0, 1)}
        </span>
        <div className="min-w-0 flex-1">
          <h3 id={`verdict-${report.profile_id}`} className="text-lg font-bold leading-tight">
            {name}
          </h3>
          <p className="mt-0.5 text-sm font-semibold">{t(`overall.${report.overall}`)}</p>
        </div>
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={report.overall}
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.7 }}
            className="inline-flex"
          >
            <StateBadge state={report.overall} unknownKind={worst?.state === "unknown" ? worst.unknown_kind : null} size="lg" />
          </motion.span>
        </AnimatePresence>
      </header>
      <div className="space-y-3 border-b border-line px-4 py-3 sm:px-5">
        <p className="text-sm leading-relaxed">
          <span className="sr-only">{t("result.summary.label")}: </span>
          {profileSummary(report, name, lang)}
        </p>
        <ReadAloudButton getText={(mode, readLang) => speechScript(report, profile, readLang, mode)} />
      </div>
      <motion.ul
        key={report.profile_id}
        className="divide-y divide-line"
        initial="hidden"
        animate="visible"
        variants={{ visible: { transition: { staggerChildren: 0.07 } } }}
      >
        {results.map((result) => (
          <ResultCard
            key={result.restriction_id}
            result={result}
            label={restrictionName(result.restriction_id)}
            changed={changed.includes(verdictKey(report.profile_id, result.restriction_id))}
          />
        ))}
      </motion.ul>
    </article>
  );
}
