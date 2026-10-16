import { CircleCheck, GitCompareArrows, Pencil } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { EditTarget } from "../label/CorrectionEditor";
import { confirmsPrintedNumber, editTargetFor } from "../../lib/confirmations";
import { formatNumber, joinWithAnd } from "../../lib/format";
import { restrictionLabel } from "../../lib/restrictionLabel";
import type { Contradiction, LabelExtraction, Profile } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { EvidenceChips } from "../evidence/EvidenceChip";
import { Message } from "../ui/Message";

interface ContradictionsPanelProps {
  contradictions: Contradiction[];
  extraction: LabelExtraction;
  profiles: Profile[];
  onCheck: (contradiction: Contradiction) => void;
  onFix: (target: EditTarget) => void;
}

/**
 * "These don't agree": every contradiction the engine found, with both sides' words on the photo, the
 * verdicts it touches, and two ways to settle it — correct a misread, or say it was checked on the pack (for a
 * disputed number: "the pack says this number"). Both are saved with the scan and recheck every verdict.
 */
export function ContradictionsPanel({ contradictions, extraction, profiles, onCheck, onFix }: ContradictionsPanelProps) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  if (contradictions.length === 0) return null;

  const affected = (item: Contradiction) =>
    joinWithAnd(
      item.affects.flatMap((ref) => {
        const profile = profiles.find((candidate) => candidate.profile_id === ref.profile_id);
        const restriction = profile?.restrictions.find((candidate) => candidate.id === ref.restriction_id);
        return profile && restriction ? [`${profile.name} · ${restrictionLabel(restriction.key, restriction.label, lang)}`] : [];
      }),
      lang,
    );

  return (
    <section aria-labelledby="contradictions-title" className="card overflow-hidden shadow-[inset_3px_0_0_var(--possible)]">
      <header className="flex items-start gap-3 border-b border-line p-4">
        <GitCompareArrows className="mt-0.5 size-5 shrink-0 text-possible" aria-hidden="true" />
        <div>
          <h2 id="contradictions-title" className="font-bold">
            {t("contradictions.title")} <span className="text-text-dim">({contradictions.length})</span>
          </h2>
          <p className="mt-1 text-sm text-text-dim">{t("contradictions.body")}</p>
        </div>
      </header>
      <ul className="divide-y divide-line">
        {contradictions.map((item) => {
          const done = item.checked === true;
          const printed = confirmsPrintedNumber(extraction, item);
          const target = item.field_path ? editTargetFor(extraction, item.field_path) : null;
          const affects = affected(item);
          return (
            <li key={item.id} className="p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-chip px-2 py-0.5 text-[0.7rem] font-semibold ${
                    done ? "bg-not-listed/15 text-not-listed" : "bg-possible/15 text-possible"
                  }`}
                >
                  {t(done ? "contradictions.checked" : "contradictions.open")}
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed">
                <Message messageKey={item.message_key} params={item.message_params} />
              </p>
              <EvidenceChips evidence={item.evidence} state="possible" className="mt-2" />
              {affects && <p className="mt-2 text-xs text-text-dim">{t("contradictions.affects", { list: affects })}</p>}
              <div className="mt-3 flex flex-wrap gap-2">
                {target && (
                  <button
                    type="button"
                    onClick={() => onFix(target)}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-chip bg-surface-2 px-3 text-xs font-semibold touch:min-h-11"
                  >
                    <Pencil className="size-3.5" aria-hidden="true" />
                    {t("contradictions.fix")}
                  </button>
                )}
                {!done && (
                  <button
                    type="button"
                    onClick={() => onCheck(item)}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-chip bg-surface-2 px-3 text-xs font-semibold touch:min-h-11"
                  >
                    <CircleCheck className="size-3.5" aria-hidden="true" />
                    {printed
                      ? t("contradictions.confirmValue", { value: formatNumber(printed.value, lang) })
                      : t("contradictions.check")}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
