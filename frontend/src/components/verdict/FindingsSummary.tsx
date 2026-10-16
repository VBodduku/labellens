import { useTranslation } from "react-i18next";
import type { Contradiction, ProfileReport } from "../../shared/contract";

/**
 * What the selected person's result rests on, in four kinds the rest of the screen keeps apart:
 * confirmed (a conflict or "not listed" the label itself establishes), uncertain ("Check this"),
 * missing (unknown) and disagreements not yet checked on the pack.
 */
export function FindingsSummary({ report, contradictions }: { report: ProfileReport; contradictions: Contradiction[] }) {
  const { t } = useTranslation();
  const count = (states: string[]) => report.results.filter((result) => states.includes(result.state)).length;
  const open = contradictions.filter(
    (item) => !item.checked && item.affects.some((ref) => ref.profile_id === report.profile_id),
  ).length;
  const items = [
    { key: "confirmed", value: count(["conflict", "not_listed"]), className: "text-text" },
    { key: "uncertain", value: count(["possible"]), className: "text-possible" },
    { key: "missing", value: count(["unknown"]), className: "text-unknown" },
    { key: "contradictions", value: open, className: "text-possible" },
  ];
  return (
    <dl aria-label={t("findings.label")} className="grid grid-cols-4 gap-2 text-center">
      {items.map((item) => (
        <div key={item.key} className="rounded-xl bg-surface-2 px-2 py-2">
          <dt className="text-[0.7rem] font-semibold text-text-dim">{t(`findings.${item.key}`)}</dt>
          <dd className={`text-lg font-bold ${item.className}`}>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
