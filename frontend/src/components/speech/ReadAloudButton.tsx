import { Square, Volume2 } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { isSynthesisSupported, loadVoices, pickVoice, speak, stopSpeaking } from "../../lib/speech";
import type { ReadAloudMode } from "../../lib/speechScript";
import type { Lang } from "../../shared/contract";
import { useUiStore } from "../../store/ui";

const RATES = [0.8, 1, 1.2] as const;

interface ReadAloudButtonProps {
  /** Text to speak for a mode in a language (called again with "en" for the English fallback). */
  getText: (mode: ReadAloudMode, lang: Lang) => string;
  /** Offer Short and Full; a single button reads the full text otherwise. */
  modes?: boolean;
}

/**
 * Read-aloud with Short / Full modes, Stop, and a speed setting. Picks the best voice for the language and,
 * when the device has none (common for Telugu/Hindi on desktops), says so and offers English instead.
 */
export function ReadAloudButton({ getText, modes = true }: ReadAloudButtonProps) {
  const { t } = useTranslation();
  const id = useId();
  const { lang, voiceRate, setVoiceRate, speakingId, setSpeaking } = useUiStore();
  const [missingVoice, setMissingVoice] = useState<ReadAloudMode | null>(null);
  const speaking = speakingId === id;

  useEffect(
    () => () => {
      if (useUiStore.getState().speakingId === id) {
        stopSpeaking();
        useUiStore.getState().setSpeaking(null);
      }
    },
    [id],
  );

  if (!isSynthesisSupported()) return null;

  async function read(mode: ReadAloudMode, readLang: Lang) {
    const voices = await loadVoices();
    const voice = pickVoice(voices, readLang);
    if (!voice && readLang !== "en") {
      setMissingVoice(mode);
      return;
    }
    setMissingVoice(null);
    setSpeaking(id);
    speak(getText(mode, readLang), readLang, voice, voiceRate, () => {
      if (useUiStore.getState().speakingId === id) setSpeaking(null);
    });
  }

  function stop() {
    stopSpeaking();
    setSpeaking(null);
  }

  const nextRate = RATES[(RATES.indexOf(voiceRate as (typeof RATES)[number]) + 1) % RATES.length] ?? 1;
  const chip = "inline-flex min-h-10 items-center gap-1.5 rounded-chip px-3 text-xs font-semibold transition-colors duration-fast";

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {speaking ? (
        <button type="button" onClick={stop} className={`${chip} bg-text text-bg`}>
          <Square className="size-3.5" aria-hidden="true" />
          {t("speech.stop")}
        </button>
      ) : modes ? (
        <>
          <button type="button" onClick={() => void read("short", lang)} className={`${chip} bg-surface-2 text-text hover:bg-line`}>
            <Volume2 className="size-4" aria-hidden="true" />
            {t("speech.readShort")}
          </button>
          <button type="button" onClick={() => void read("full", lang)} className={`${chip} bg-surface-2 text-text hover:bg-line`}>
            {t("speech.readFull")}
          </button>
        </>
      ) : (
        <button type="button" onClick={() => void read("full", lang)} className={`${chip} bg-surface-2 text-text hover:bg-line`}>
          <Volume2 className="size-4" aria-hidden="true" />
          {t("speech.readAloud")}
        </button>
      )}
      <button
        type="button"
        onClick={() => setVoiceRate(nextRate)}
        aria-label={t("speech.rate", { rate: voiceRate })}
        title={t("speech.rate", { rate: voiceRate })}
        className={`${chip} min-w-11 justify-center text-text-dim hover:text-text`}
      >
        {voiceRate}×
      </button>
      {missingVoice && (
        <p role="status" className="flex w-full flex-wrap items-center gap-2 text-xs text-text-dim">
          {t("speech.noVoice", { language: t(`lang.${lang}`) })}
          <button type="button" onClick={() => void read(missingVoice, "en")} className="font-semibold text-beam underline-offset-2 hover:underline">
            {t("speech.readEnglish")}
          </button>
        </p>
      )}
    </div>
  );
}
