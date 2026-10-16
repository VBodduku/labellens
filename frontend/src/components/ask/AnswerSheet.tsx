import { ShieldQuestion } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ApiError } from "../../api";
import type { AskResponse, Profile } from "../../shared/contract";
import { EvidenceChips } from "../evidence/EvidenceChip";
import { ReadAloudButton } from "../speech/ReadAloudButton";
import { Button } from "../ui/Button";
import { ErrorNotice } from "../ui/ErrorNotice";
import { Sheet } from "../ui/Sheet";
import { Skeleton } from "../ui/Skeleton";
import { ToolTrace } from "./ToolTrace";

export type AnswerState =
  | { status: "loading"; question: string }
  | { status: "done"; question: string; response: AskResponse }
  | { status: "error"; question: string; error: ApiError };

interface AnswerSheetProps {
  state: AnswerState | null;
  profiles: Profile[];
  onClose: () => void;
  onRetry: () => void;
}

/**
 * The assistant's answer: grounded text with read-aloud, the label evidence it used (tap to see it on the
 * photo), and the steps it took. Refusals and ungrounded answers are styled as such.
 */
export function AnswerSheet({ state, profiles, onClose, onRetry }: AnswerSheetProps) {
  const { t } = useTranslation();
  return (
    <Sheet open={state !== null} title={t("ask.title")} onClose={onClose} wide>
      {state && (
        <div className="space-y-5">
          <p className="rounded-xl bg-surface-2 px-4 py-3 text-sm">
            <span className="sr-only">{t("ask.yourQuestion")}: </span>
            <q>{state.question}</q>
          </p>

          {state.status === "loading" && (
            <div role="status" aria-live="polite" className="space-y-2">
              <p className="text-sm font-semibold text-text-dim">{t("ask.thinking")}</p>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-4 w-3/5" />
            </div>
          )}

          {state.status === "error" && <ErrorNotice error={state.error} actions={<Button onClick={onRetry}>{t("common.retry")}</Button>} />}

          {state.status === "done" && (
            <>
              {!state.response.grounded || state.response.refusal ? (
                <div role="status" className="flex gap-3 rounded-card bg-possible/10 p-4 shadow-[inset_0_0_0_1px_var(--possible)]">
                  <ShieldQuestion className="mt-0.5 size-5 shrink-0 text-possible" aria-hidden="true" />
                  <div>
                    <p className="text-sm font-semibold">{state.response.refusal === "medical_advice" ? t("ask.refusal.medical") : t("ask.refusal.ungrounded")}</p>
                    <p className="mt-1 text-sm leading-relaxed">{state.response.answer}</p>
                  </div>
                </div>
              ) : (
                <p aria-live="polite" className="text-base leading-relaxed">
                  {state.response.answer}
                </p>
              )}
              <ReadAloudButton modes={false} getText={() => state.response.answer} />
              {state.response.evidence.length > 0 && (
                <div onClickCapture={onClose}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-dim">{t("ask.evidence")}</p>
                  <EvidenceChips evidence={state.response.evidence} state={null} className="mt-2" />
                </div>
              )}
              <ToolTrace calls={state.response.tool_calls} profiles={profiles} />
            </>
          )}
        </div>
      )}
    </Sheet>
  );
}
