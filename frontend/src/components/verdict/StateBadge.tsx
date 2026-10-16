import { useTranslation } from "react-i18next";
import { stateLabelKey } from "../../lib/verdict";
import type { UnknownKind, VerdictState } from "../../shared/contract";
import { StateIcon } from "./StateIcon";

type BadgeSize = "sm" | "md" | "lg";

/** Fill style per state: conflict/possible solid, not listed outline, unknown hatched (never colour alone). */
const STATE_STYLES: Record<VerdictState, string> = {
  conflict: "bg-conflict text-on-verdict",
  possible: "bg-possible text-on-verdict",
  not_listed: "text-not-listed shadow-[inset_0_0_0_1.5px_var(--not-listed)]",
  unknown: "hatch text-unknown shadow-[inset_0_0_0_1.5px_var(--unknown)] bg-surface",
};

const SIZE_STYLES: Record<BadgeSize, { badge: string; icon: string }> = {
  sm: { badge: "min-h-6 gap-1 px-2 text-[0.72rem]", icon: "size-3.5" },
  md: { badge: "min-h-7 gap-1.5 px-2.5 text-xs", icon: "size-4" },
  lg: { badge: "min-h-9 gap-2 px-3.5 text-sm", icon: "size-5" },
};

interface StateBadgeProps {
  state: VerdictState;
  unknownKind?: UnknownKind | null;
  size?: BadgeSize;
  className?: string;
}

export function StateBadge({ state, unknownKind, size = "md", className = "" }: StateBadgeProps) {
  const { t } = useTranslation();
  const sizes = SIZE_STYLES[size];
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-chip font-bold tracking-wide ${STATE_STYLES[state]} ${sizes.badge} ${className}`}
      data-state={state}
    >
      <StateIcon state={state} className={sizes.icon} />
      <span>{t(stateLabelKey(state, unknownKind))}</span>
    </span>
  );
}
