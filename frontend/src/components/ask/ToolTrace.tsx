import { Wrench } from "lucide-react";
import { useTranslation } from "react-i18next";
import { describeToolCall } from "../../lib/toolTrace";
import type { Profile, ToolCallTrace } from "../../shared/contract";
import { useUiStore } from "../../store/ui";

/** The steps the assistant took, in plain language, so people can see the answer came from the label. */
export function ToolTrace({ calls, profiles }: { calls: ToolCallTrace[]; profiles: Profile[] }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  if (calls.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-text-dim">{t("ask.steps")}</p>
      <ul className="mt-2 flex flex-wrap gap-1.5">
        {calls.map((call, index) => (
          <li
            key={`${call.tool}:${index}`}
            title={call.result_summary}
            className="inline-flex min-h-8 items-center gap-1.5 rounded-chip bg-surface-2 px-3 text-xs text-text-dim"
          >
            <Wrench className="size-3.5" aria-hidden="true" />
            {describeToolCall(call, profiles, lang)}
          </li>
        ))}
      </ul>
    </div>
  );
}
