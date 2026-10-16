import { SendHorizontal } from "lucide-react";
import { lazy, Suspense, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, isApiError } from "../../api";
import type { Profile, ScanResult } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { MicButton } from "../speech/MicButton";
import { useLatch } from "../../lib/useLatch";
import type { AnswerState } from "./AnswerSheet";

const AnswerSheet = lazy(() => import("./AnswerSheet").then((module) => ({ default: module.AnswerSheet })));

/** "Ask the label" (§5.4): sticky question bar, typed or spoken, answered by the agent from this scan only. */
export function AskBar({ result, profiles }: { result: ScanResult; profiles: Profile[] }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const [question, setQuestion] = useState("");
  const [micError, setMicError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<AnswerState | null>(null);
  const inflight = useRef<AbortController | null>(null);
  const disabled = result.reports.length === 0;
  const sheetMounted = useLatch(answer !== null);

  async function ask(text: string) {
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    setAnswer({ status: "loading", question: text });
    try {
      const response = await api.ask({ question: text, lang, scan: result, profiles }, { signal: controller.signal });
      setAnswer({ status: "done", question: text, response });
    } catch (error) {
      if (isApiError(error) && error.code === "ABORTED") return;
      setAnswer({ status: "error", question: text, error: isApiError(error) ? error : new ApiError("INTERNAL", String(error)) });
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || disabled) return;
    setQuestion("");
    void ask(text);
  }

  function close() {
    inflight.current?.abort();
    setAnswer(null);
  }

  return (
    <>
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-bg/90 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl">
        <form onSubmit={submit} className="page-gutter mx-auto flex max-w-page items-center gap-2">
          <label htmlFor="ask-input" className="sr-only">
            {t("ask.label")}
          </label>
          <input
            id="ask-input"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            disabled={disabled}
            placeholder={disabled ? t("ask.needProfiles") : t("ask.placeholder")}
            autoComplete="off"
            enterKeyHint="send"
            className="min-h-12 min-w-0 flex-1 rounded-chip bg-surface-2 px-4 text-base shadow-[inset_0_0_0_1px_var(--line)] placeholder:text-text-dim/80 focus:shadow-[inset_0_0_0_2px_var(--beam)] focus:outline-none disabled:opacity-60"
          />
          <MicButton lang={lang} onText={(spoken) => setQuestion(spoken)} onError={setMicError} disabled={disabled} />
          <button
            type="submit"
            disabled={disabled || !question.trim()}
            aria-label={t("ask.send")}
            className="flex size-12 shrink-0 items-center justify-center rounded-full bg-[image:var(--beam-gradient)] text-on-beam disabled:opacity-35"
          >
            <SendHorizontal className="size-5" aria-hidden="true" />
          </button>
        </form>
        {micError && (
          <p role="alert" className="page-gutter mx-auto mt-1 max-w-page text-xs text-conflict">
            {micError}
          </p>
        )}
      </div>
      {sheetMounted && (
        <Suspense fallback={null}>
          <AnswerSheet state={answer} profiles={profiles} onClose={close} onRetry={() => answer && void ask(answer.question)} />
        </Suspense>
      )}
    </>
  );
}
