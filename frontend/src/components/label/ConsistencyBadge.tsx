import { CircleAlert, CircleCheck, CircleDashed } from "lucide-react";
import type { ConsistencyCheck } from "../../shared/contract";
import { Message } from "../ui/Message";

const STYLES = {
  consistent: { Icon: CircleCheck, className: "text-not-listed shadow-[inset_0_0_0_1px_var(--not-listed)]" },
  inconsistent: { Icon: CircleAlert, className: "bg-possible/10 text-possible shadow-[inset_0_0_0_1px_var(--possible)]" },
  insufficient_data: { Icon: CircleDashed, className: "text-text-dim shadow-[inset_0_0_0_1px_var(--line)]" },
} as const;

/** The energy cross-check: do the calories add up from the listed macros? */
export function ConsistencyBadge({ consistency }: { consistency: ConsistencyCheck }) {
  const { Icon, className } = STYLES[consistency.status];
  const deviation = consistency.deviation_pct === null || consistency.deviation_pct === undefined ? undefined : Math.round(consistency.deviation_pct);
  return (
    <p className={`flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm ${className}`}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <Message messageKey={consistency.message_key} params={deviation === undefined ? {} : { deviation }} />
    </p>
  );
}
