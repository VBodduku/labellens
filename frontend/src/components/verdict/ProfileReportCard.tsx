import { useTranslation } from "react-i18next";
import { sortWorstFirst } from "../../lib/verdict";
import type { Evidence, Profile, ProfileReport } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { Message } from "../ui/Message";
import { StateBadge } from "./StateBadge";

function EvidenceChips({ evidence }: { evidence: Evidence[] }) {
  const { t } = useTranslation();
  const shown = evidence.filter((item, index) => item.text && evidence.findIndex((other) => other.text === item.text) === index);
  if (shown.length === 0) return null;
  return (
    <ul aria-label={t("result.evidence.label")} className="mt-2.5 flex flex-wrap gap-1.5">
      {shown.map((item) => (
        <li
          key={`${item.image_id}:${item.text}`}
          className={`evidence-text inline-flex min-h-7 items-center rounded-md px-2 text-xs ${
            item.status === "unverified"
              ? "text-text-dim shadow-[inset_0_0_0_1px_var(--line)]"
              : item.status === "approximate"
                ? "bg-surface-2 text-text [outline:1px_dashed_var(--text-dim)]"
                : "bg-surface-2 text-text"
          }`}
        >
          {item.text}
          {item.status === "unverified" && <span className="ml-1.5 font-body">· {t("result.evidence.unverified")}</span>}
        </li>
      ))}
    </ul>
  );
}

/** One family member's verdict: overall state, summary when it matches the language, results worst-first. */
export function ProfileReportCard({ report, profile }: { report: ProfileReport; profile: Profile | undefined }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const results = sortWorstFirst(report.results);
  const worst = results[0];
  const name = profile?.name ?? report.profile_id;

  return (
    <article className="card overflow-hidden">
      <header className="flex items-center gap-3 border-b border-line p-4 sm:p-5">
        <span
          aria-hidden="true"
          className="flex size-10 shrink-0 items-center justify-center rounded-full font-bold text-[#0b0d12]"
          style={{ background: profile?.color ?? "var(--beam)" }}
        >
          {name.slice(0, 1)}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-bold">{name}</h3>
          <p className="text-sm text-text-dim">{t(`overall.${report.overall}`)}</p>
        </div>
        <StateBadge state={report.overall} unknownKind={worst?.state === "unknown" ? worst.unknown_kind : null} />
      </header>
      {report.summary && report.summary_lang === lang && (
        <p className="border-b border-line px-4 py-3 text-sm leading-relaxed sm:px-5">
          <span className="sr-only">{t("result.summary.label")}: </span>
          {report.summary}
        </p>
      )}
      <ul className="divide-y divide-line">
        {results.map((result) => {
          const restriction = profile?.restrictions.find((candidate) => candidate.id === result.restriction_id);
          return (
            <li key={result.restriction_id} className="p-4 sm:p-5">
              <div className="flex flex-wrap items-center gap-2">
                <StateBadge state={result.state} unknownKind={result.unknown_kind} size="sm" />
                <span className="text-sm font-semibold">{restriction?.label ?? result.restriction_id}</span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-text-dim">
                <Message messageKey={result.message_key} params={result.message_params} />
              </p>
              <EvidenceChips evidence={result.evidence} />
            </li>
          );
        })}
      </ul>
    </article>
  );
}
