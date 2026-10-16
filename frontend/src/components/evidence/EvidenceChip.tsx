import { LocateFixed } from "lucide-react";
import { useTranslation } from "react-i18next";
import { stateColor } from "../../lib/verdict";
import type { Evidence, VerdictState } from "../../shared/contract";
import { useUiStore } from "../../store/ui";

interface EvidenceChipProps {
  evidence: Evidence;
  state: VerdictState | null;
}

/**
 * The words behind a flag, exactly as printed. Tapping one zooms the photo to them (any chip, anywhere).
 * Evidence the backend could not locate shows "Couldn't locate on photo" instead of offering a zoom.
 */
export function EvidenceChip({ evidence, state }: EvidenceChipProps) {
  const { t } = useTranslation();
  const focusEvidence = useUiStore((store) => store.focusEvidence);
  const locatable = evidence.status !== "unverified" && Boolean(evidence.box);

  if (!locatable) {
    return (
      <span className="evidence-text inline-flex min-h-8 items-center gap-1.5 rounded-md px-2 text-xs text-text-dim shadow-[inset_0_0_0_1px_var(--line)]">
        <span lang="">{evidence.text}</span>
        <span className="font-body">· {t("result.evidence.unverified")}</span>
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={() => focusEvidence(evidence, state)}
      aria-label={t("result.evidence.show", { text: evidence.text })}
      title={evidence.status === "approximate" ? t("result.evidence.approximate") : undefined}
      className={`evidence-text group inline-flex min-h-8 items-center gap-1.5 rounded-md bg-surface-2 py-1 pl-2 pr-2.5 text-left text-xs text-text transition-[transform,background-color] duration-fast ease-out hover:bg-line active:scale-[0.97] ${
        evidence.status === "approximate" ? "[outline:1px_dashed_var(--text-dim)] [outline-offset:-1px]" : ""
      }`}
      style={{ boxShadow: `inset 2px 0 0 ${stateColor(state)}` }}
    >
      <LocateFixed className="size-3.5 shrink-0 text-text-dim group-hover:text-text" aria-hidden="true" />
      <span lang="">{evidence.text}</span>
    </button>
  );
}

/** Evidence chips for one result: located ones first, duplicates (same text and box) removed. */
export function EvidenceChips({ evidence, state, className = "" }: { evidence: Evidence[]; state: VerdictState | null; className?: string }) {
  const { t } = useTranslation();
  const seen = new Set<string>();
  const shown = evidence.filter((item) => {
    const key = `${item.image_id}:${item.text}:${item.box?.x ?? ""}:${item.box?.y ?? ""}`;
    if (!item.text || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (shown.length === 0) return null;
  return (
    <ul aria-label={t("result.evidence.label")} className={`flex flex-wrap gap-1.5 ${className}`}>
      {shown.map((item, index) => (
        <li key={`${item.image_id}:${item.text}:${index}`}>
          <EvidenceChip evidence={item} state={state} />
        </li>
      ))}
    </ul>
  );
}
