import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { setLanguage } from "../i18n";
import { isLang } from "../i18n/resources";
import type { Evidence, Lang, VerdictState } from "../shared/contract";

export type ThemeChoice = "system" | "light" | "dark";

/**
 * Evidence the viewer should zoom to. `state` colours the highlight (null = neutral, e.g. an ingredient);
 * `nonce` re-triggers the focus animation when the same chip is tapped again.
 */
export interface FocusedEvidence {
  evidence: Evidence;
  state: VerdictState | null;
  nonce: number;
}

const THEME_CYCLE: ThemeChoice[] = ["system", "light", "dark"];

interface UiState {
  lang: Lang;
  theme: ThemeChoice;
  selectedProfileId: string | null;
  focusedEvidence: FocusedEvidence | null;
  voiceRate: number;
  setLang: (lang: Lang) => void;
  setTheme: (theme: ThemeChoice) => void;
  cycleTheme: () => void;
  selectProfile: (profileId: string | null) => void;
  focusEvidence: (evidence: Evidence, state: VerdictState | null) => void;
  clearFocus: () => void;
  setVoiceRate: (rate: number) => void;
}

export function detectLang(languages: readonly string[] = globalThis.navigator?.languages ?? []): Lang {
  for (const language of languages) {
    const base = language.slice(0, 2).toLowerCase();
    if (isLang(base)) return base;
  }
  return "en";
}

/** html[data-theme] drives the light/dark tokens; "system" removes it so the media query decides. */
export function applyTheme(theme: ThemeChoice): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      lang: detectLang(),
      theme: "system",
      selectedProfileId: null,
      focusedEvidence: null,
      voiceRate: 1,
      setLang: (lang) => {
        setLanguage(lang);
        set({ lang });
      },
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
      cycleTheme: () => {
        const next = THEME_CYCLE[(THEME_CYCLE.indexOf(get().theme) + 1) % THEME_CYCLE.length] ?? "system";
        get().setTheme(next);
      },
      selectProfile: (selectedProfileId) => set({ selectedProfileId }),
      focusEvidence: (evidence, state) =>
        set({ focusedEvidence: { evidence, state, nonce: (get().focusedEvidence?.nonce ?? 0) + 1 } }),
      clearFocus: () => set({ focusedEvidence: null }),
      setVoiceRate: (voiceRate) => set({ voiceRate: Math.min(1.5, Math.max(0.6, voiceRate)) }),
    }),
    {
      name: "labellens.ui",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ lang: state.lang, theme: state.theme, voiceRate: state.voiceRate }),
    },
  ),
);
