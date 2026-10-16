import { Mic, MicOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { createRecognizer, isRecognitionSupported } from "../../lib/speech";
import type { Lang } from "../../shared/contract";

interface MicButtonProps {
  lang: Lang;
  /** Live transcript (interim while speaking, final at the end). */
  onText: (text: string, final: boolean) => void;
  onError: (message: string | null) => void;
  disabled?: boolean;
  className?: string;
}

/** Voice input in the current language; not rendered at all where the browser has no speech recognition. */
export function MicButton({ lang, onText, onError, disabled = false, className = "" }: MicButtonProps) {
  const { t } = useTranslation();
  const [listening, setListening] = useState(false);
  const recognizer = useRef<ReturnType<typeof createRecognizer>>(null);

  useEffect(() => () => recognizer.current?.stop(), []);

  if (!isRecognitionSupported()) return null;

  function toggle() {
    if (listening) {
      recognizer.current?.stop();
      return;
    }
    onError(null);
    recognizer.current = createRecognizer(lang, {
      onText,
      onError: (key) => onError(t(key)),
      onEnd: () => setListening(false),
    });
    try {
      recognizer.current?.start();
      setListening(true);
    } catch {
      onError(t("speech.error.generic"));
    }
  }

  const label = listening ? t("speech.stopListening") : t("speech.listen", { language: t(`lang.${lang}`) });
  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      aria-label={label}
      aria-pressed={listening}
      title={label}
      className={`relative flex size-11 shrink-0 items-center justify-center rounded-full transition-colors duration-fast disabled:opacity-40 ${
        listening ? "bg-conflict text-on-verdict" : "bg-surface-2 text-text hover:bg-line"
      } ${className}`}
    >
      {listening && <span aria-hidden="true" className="absolute inset-0 animate-ping rounded-full bg-conflict/40 motion-reduce:animate-none" />}
      {listening ? <MicOff className="relative size-5" aria-hidden="true" /> : <Mic className="relative size-5" aria-hidden="true" />}
    </button>
  );
}
