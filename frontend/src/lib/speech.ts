import type { Lang } from "../shared/contract";

/*
 * Thin typed wrappers over the Web Speech API. TypeScript's DOM lib has no SpeechRecognition types, so the
 * few members we use are declared here (this module is the only place that touches the raw API).
 */

export const SPEECH_LANG: Record<Lang, string> = { en: "en-IN", hi: "hi-IN", te: "te-IN" };

interface RecognitionAlternative {
  transcript: string;
}
interface RecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: RecognitionAlternative | undefined;
}
interface RecognitionResultList {
  readonly length: number;
  [index: number]: RecognitionResult | undefined;
}
interface RecognitionEvent {
  readonly results: RecognitionResultList;
}
interface RecognitionErrorEvent {
  readonly error: string;
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
type RecognitionConstructor = new () => Recognition;

function recognitionConstructor(): RecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const speechWindow = window as unknown as {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

export function isRecognitionSupported(): boolean {
  return recognitionConstructor() !== null;
}

export type SpeechErrorKey = "speech.error.notAllowed" | "speech.error.noSpeech" | "speech.error.network" | "speech.error.generic";

/** Maps recognition error codes to the message keys we show (null = not worth telling the user). */
export function recognitionErrorKey(code: string): SpeechErrorKey | null {
  if (code === "aborted") return null;
  if (code === "not-allowed" || code === "service-not-allowed") return "speech.error.notAllowed";
  if (code === "no-speech") return "speech.error.noSpeech";
  if (code === "network") return "speech.error.network";
  return "speech.error.generic";
}

export const SILENCE_MS = 2000;

interface RecognizerHandlers {
  /** Full transcript so far (final + interim words). */
  onText: (text: string, final: boolean) => void;
  onError: (key: SpeechErrorKey) => void;
  onEnd: () => void;
}

/** Voice input in the chosen language with live interim text; stops itself after ~2 s of silence. */
export function createRecognizer(lang: Lang, handlers: RecognizerHandlers): { start: () => void; stop: () => void } | null {
  const Constructor = recognitionConstructor();
  if (!Constructor) return null;
  const recognition = new Constructor();
  recognition.lang = SPEECH_LANG[lang];
  recognition.interimResults = true;
  recognition.continuous = true;
  recognition.maxAlternatives = 1;
  let silenceTimer: number | undefined;

  const armSilenceTimer = () => {
    window.clearTimeout(silenceTimer);
    silenceTimer = window.setTimeout(() => recognition.stop(), SILENCE_MS);
  };

  recognition.onresult = (event) => {
    let text = "";
    let final = true;
    for (let index = 0; index < event.results.length; index += 1) {
      const result = event.results[index];
      if (!result) continue;
      text += result[0]?.transcript ?? "";
      if (!result.isFinal) final = false;
    }
    handlers.onText(text.trim(), final);
    armSilenceTimer();
  };
  recognition.onerror = (event) => {
    const key = recognitionErrorKey(event.error);
    if (key) handlers.onError(key);
  };
  recognition.onend = () => {
    window.clearTimeout(silenceTimer);
    handlers.onEnd();
  };

  return {
    start: () => {
      recognition.start();
      armSilenceTimer();
    },
    stop: () => {
      window.clearTimeout(silenceTimer);
      recognition.stop();
    },
  };
}

export interface VoiceLike {
  lang: string;
  name: string;
}

/** Best voice for a language: exact xx-IN first, then any voice whose language starts with xx. */
export function pickVoice<T extends VoiceLike>(voices: readonly T[], lang: Lang): T | null {
  const normalise = (value: string) => value.replace("_", "-").toLowerCase();
  const exact = SPEECH_LANG[lang].toLowerCase();
  return (
    voices.find((voice) => normalise(voice.lang) === exact) ??
    voices.find((voice) => normalise(voice.lang).startsWith(`${lang}-`) || normalise(voice.lang) === lang) ??
    null
  );
}

export function isSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/** Voices load asynchronously in Chrome; wait for `voiceschanged` (bounded so the UI never hangs). */
export function loadVoices(timeoutMs = 1500): Promise<SpeechSynthesisVoice[]> {
  if (!isSynthesisSupported()) return Promise.resolve([]);
  const synthesis = window.speechSynthesis;
  const ready = synthesis.getVoices();
  if (ready.length > 0) return Promise.resolve(ready);
  return new Promise((resolve) => {
    const done = () => {
      synthesis.removeEventListener("voiceschanged", done);
      window.clearTimeout(timer);
      resolve(synthesis.getVoices());
    };
    const timer = window.setTimeout(done, timeoutMs);
    synthesis.addEventListener("voiceschanged", done);
  });
}

/** Splits long text into sentences: Chrome cuts single utterances off after ~15 s. */
export function sentenceChunks(text: string): string[] {
  return text
    .split(/(?<=[.!?।])\s+/u)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function stopSpeaking(): void {
  if (isSynthesisSupported()) window.speechSynthesis.cancel();
}

/** Speaks text (never overlapping: anything already speaking is cancelled first). */
export function speak(text: string, lang: Lang, voice: SpeechSynthesisVoice | null, rate: number, onEnd: () => void): void {
  if (!isSynthesisSupported()) {
    onEnd();
    return;
  }
  stopSpeaking();
  const chunks = sentenceChunks(text);
  if (chunks.length === 0) {
    onEnd();
    return;
  }
  chunks.forEach((chunk, index) => {
    const utterance = new SpeechSynthesisUtterance(chunk);
    utterance.lang = SPEECH_LANG[lang];
    if (voice) utterance.voice = voice;
    utterance.rate = rate;
    if (index === chunks.length - 1) {
      utterance.onend = onEnd;
      utterance.onerror = onEnd;
    }
    window.speechSynthesis.speak(utterance);
  });
}
