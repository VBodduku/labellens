import { CircleCheck, CircleX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { confirmationCorrections, type ConfirmPrompt as Prompt, type ConfirmValue } from "../../lib/confirmations";
import { useScanStore } from "../../store/scan";
import { useUiStore } from "../../store/ui";
import { Message } from "../ui/Message";

/**
 * Asks the user to settle an unclear ingredient from the pack itself ("Check the pack: does INS 471 contain
 * animal-derived?"). The answer is saved as a correction and every verdict is rechecked; the engine then
 * reports it as "Checked by you", never as its own finding.
 */
export function ConfirmPrompt({ prompt }: { prompt: Prompt }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const extraction = useScanStore((state) => state.result?.extraction);
  const busy = useScanStore((state) => state.status === "rechecking");
  const addCorrections = useScanStore((state) => state.addCorrections);

  function answer(value: ConfirmValue) {
    if (extraction) void addCorrections(confirmationCorrections(extraction, prompt, value), lang);
  }

  return (
    <div className="mt-3 rounded-xl bg-surface-2 p-3">
      <p className="text-sm font-semibold">
        <Message messageKey="confirm.question" params={{ term: prompt.term, category: prompt.categories.join("|") }} />
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {prompt.allowPresent && (
          <button
            type="button"
            disabled={busy}
            onClick={() => answer("present")}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-chip bg-conflict/15 px-3 text-xs font-semibold text-conflict touch:min-h-11 disabled:opacity-50"
          >
            <CircleX className="size-3.5" aria-hidden="true" />
            {t("confirm.yes")}
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => answer("absent")}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-chip bg-not-listed/15 px-3 text-xs font-semibold text-not-listed touch:min-h-11 disabled:opacity-50"
        >
          <CircleCheck className="size-3.5" aria-hidden="true" />
          {t("confirm.no")}
        </button>
      </div>
    </div>
  );
}
