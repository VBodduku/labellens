import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import type { Lang } from "../shared/contract";
import { dictionaries, loadDictionary } from "./resources";

/**
 * Keys are flat and dotted (`verdict.conflict.ingredient`), exactly as in shared/messages.en.json, and
 * placeholders use single braces `{name}` everywhere. Engine messages go through renderMessage().
 */
export function initI18n(lang: Lang): typeof i18next {
  if (!i18next.isInitialized) {
    void i18next.use(initReactI18next).init({
      resources: { en: { translation: dictionaries.en } },
      lng: lang,
      fallbackLng: "en",
      keySeparator: false,
      nsSeparator: false,
      interpolation: { escapeValue: false, prefix: "{", suffix: "}" },
      react: { useSuspense: false },
    });
  }
  applyDocumentLang(lang);
  return i18next;
}

export function applyDocumentLang(lang: Lang): void {
  if (typeof document !== "undefined") document.documentElement.lang = lang;
}

/** Fetches a language's strings (once) and registers them with i18next. */
export async function loadLanguage(lang: Lang): Promise<void> {
  const dictionary = await loadDictionary(lang);
  if (!i18next.hasResourceBundle(lang, "translation")) i18next.addResourceBundle(lang, "translation", dictionary, true, true);
}

export async function setLanguage(lang: Lang): Promise<void> {
  await loadLanguage(lang);
  await i18next.changeLanguage(lang);
  applyDocumentLang(lang);
}
