import { Sparkles } from "lucide-react";
import { useId, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, isApiError } from "../../api";
import { isRecognitionSupported } from "../../lib/speech";
import type { ProfileParseResponse } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { MicButton } from "../speech/MicButton";
import { Button } from "../ui/Button";
import { ErrorNotice } from "../ui/ErrorNotice";

/** "Describe your family" — a sentence (typed or spoken) that becomes proposed profiles to confirm. */
export function SentenceInput({ onParsed }: { onParsed: (response: ProfileParseResponse) => void }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const inputId = useId();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [micError, setMicError] = useState<string | null>(null);
  const inflight = useRef<AbortController | null>(null);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const sentence = text.trim();
    if (!sentence || busy) return;
    inflight.current?.abort();
    inflight.current = new AbortController();
    setBusy(true);
    setError(null);
    try {
      onParsed(await api.parseProfile({ text: sentence, lang }, { signal: inflight.current.signal }));
    } catch (failure) {
      if (!isApiError(failure) || failure.code !== "ABORTED") {
        setError(isApiError(failure) ? failure : new ApiError("INTERNAL", String(failure)));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="card p-4 sm:p-5">
      <label htmlFor={inputId} className="block font-bold">
        {t("profiles.describe.title")}
      </label>
      <p className="mt-1 text-sm text-text-dim">{t("profiles.describe.hint")}</p>
      <div className="mt-3 flex items-start gap-2">
        <textarea
          id={inputId}
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={3}
          placeholder={t("profiles.describe.placeholder")}
          className="min-h-24 min-w-0 flex-1 resize-y rounded-xl bg-surface-2 p-3 text-base shadow-[inset_0_0_0_1px_var(--line)] placeholder:text-text-dim/70 focus:shadow-[inset_0_0_0_2px_var(--beam)] focus:outline-none"
        />
        <MicButton lang={lang} onText={(spoken) => setText(spoken)} onError={setMicError} disabled={busy} />
      </div>
      {micError && (
        <p role="alert" className="mt-2 text-sm text-conflict">
          {micError}
        </p>
      )}
      {!isRecognitionSupported() && <p className="mt-2 text-xs text-text-dim">{t("speech.unsupported")}</p>}
      <Button type="submit" className="mt-3" loading={busy} disabled={!text.trim()} icon={<Sparkles className="size-4" aria-hidden="true" />}>
        {busy ? t("profiles.describe.working") : t("profiles.describe.submit")}
      </Button>
      {error && (
        <div className="mt-4">
          <ErrorNotice error={error} onRetry={() => void submit()} />
        </div>
      )}
    </form>
  );
}
