import { del as idbDel, get as idbGet, set as idbSet } from "idb-keyval";
import { create } from "zustand";
import { api, ApiError, isApiError } from "../api";
import { applyCorrections, makeCorrection } from "../lib/corrections";
import { confirmsPrintedNumber } from "../lib/confirmations";
import { createId } from "../lib/ids";
import { changedVerdicts } from "../lib/resultDiff";
import type { Contradiction, Correction, Lang, PanelHint, Profile, ScanResult } from "../shared/contract";

export const MAX_PANELS = 3;
export const LAST_SCAN_KEY = "labellens.lastScan";

export interface Panel {
  id: string;
  file: Blob;
  /** Object URL for drawing the photo; index in `panels` matches the backend's img_<index>. */
  url: string;
  hint: PanelHint;
}

export type ScanStatus = "idle" | "analysing" | "rechecking" | "done" | "error";

interface StoredScan {
  panels: { file: Blob; hint: PanelHint }[];
  result: ScanResult;
  scanProfiles: Profile[];
  corrections: Correction[];
  isDemo: boolean;
}

interface ScanState {
  panels: Panel[];
  result: ScanResult | null;
  /** Profiles the current result was computed for (the demo uses the fixture family). */
  scanProfiles: Profile[];
  /** Profiles sent with the latest analyse() call — used to retry it and to count "checking for n members". */
  attemptProfiles: Profile[];
  status: ScanStatus;
  error: ApiError | null;
  /** A failed recheck keeps the current result on screen; this says why it wasn't updated. */
  recheckError: ApiError | null;
  corrections: Correction[];
  isDemo: boolean;
  hydrated: boolean;
  /** `profile:restriction` keys whose verdict changed in the last recheck (drives the change animation). */
  changedVerdicts: string[];
  addPanel: (file: Blob, hint?: PanelHint) => void;
  retakePanel: (index: number, file: Blob) => void;
  setPanelHint: (index: number, hint: PanelHint) => void;
  removePanel: (index: number) => void;
  analyse: (input: { profiles: Profile[]; lang: Lang }) => Promise<void>;
  cancel: () => void;
  /** Engine-only re-evaluation (no new reading): after a correction, a language switch or profile edits. */
  recheck: (lang: Lang, profiles?: Profile[]) => Promise<void>;
  addCorrection: (correction: Correction, lang: Lang) => Promise<void>;
  /** Several corrections, one recheck (a confirmation covers each category of an ingredient). */
  addCorrections: (corrections: Correction[], lang: Lang) => Promise<void>;
  /**
   * "I checked the pack" for a contradiction: saved with the scan (and, for a disputed number, recorded as
   * "the pack says this number"), then every verdict is rechecked. Shown as checked straight away.
   */
  checkContradiction: (contradiction: Contradiction, lang: Lang) => Promise<void>;
  loadDemo: () => Promise<void>;
  hydrate: () => Promise<void>;
  reset: () => void;
}

let inflight: AbortController | null = null;

function makePanel(file: Blob, hint: PanelHint): Panel {
  return { id: createId("panel"), file, url: URL.createObjectURL(file), hint };
}

function revokeAll(panels: Panel[]): void {
  panels.forEach((panel) => URL.revokeObjectURL(panel.url));
}

function startRequest(): AbortSignal {
  inflight?.abort();
  inflight = new AbortController();
  return inflight.signal;
}

/** A request replaced by a newer one must not touch the store (the newer request owns the status). */
function superseded(signal: AbortSignal): boolean {
  return inflight?.signal !== signal && inflight !== null;
}

async function persist(state: ScanState): Promise<void> {
  if (!state.result) return;
  const stored: StoredScan = {
    panels: state.panels.map(({ file, hint }) => ({ file, hint })),
    result: state.result,
    scanProfiles: state.scanProfiles,
    corrections: state.corrections,
    isDemo: state.isDemo,
  };
  try {
    await idbSet(LAST_SCAN_KEY, stored);
  } catch {
    // Storage can be unavailable (private mode, quota); the in-memory result still works.
  }
}

export const useScanStore = create<ScanState>()((set, get) => {
  function failWith(error: unknown, signal: AbortSignal): void {
    if (superseded(signal)) return;
    if (isApiError(error) && error.code === "ABORTED") {
      set({ status: get().result ? "done" : "idle", error: null });
      return;
    }
    set({ status: "error", error: isApiError(error) ? error : new ApiError("INTERNAL", String(error)) });
  }

  return {
    panels: [],
    result: null,
    scanProfiles: [],
    attemptProfiles: [],
    status: "idle",
    error: null,
    recheckError: null,
    corrections: [],
    isDemo: false,
    hydrated: false,
    changedVerdicts: [],

    addPanel: (file, hint = "unknown") => {
      const { panels, isDemo } = get();
      if (isDemo) {
        revokeAll(panels);
        set({ panels: [makePanel(file, hint)], result: null, isDemo: false, corrections: [], status: "idle" });
        return;
      }
      if (panels.length >= MAX_PANELS) return;
      set({ panels: [...panels, makePanel(file, hint)] });
    },

    retakePanel: (index, file) => {
      const panels = [...get().panels];
      const previous = panels[index];
      if (!previous) return;
      URL.revokeObjectURL(previous.url);
      panels[index] = makePanel(file, previous.hint);
      set({ panels, isDemo: false });
    },

    setPanelHint: (index, hint) => {
      set({ panels: get().panels.map((panel, i) => (i === index ? { ...panel, hint } : panel)) });
    },

    removePanel: (index) => {
      const panels = [...get().panels];
      const [removed] = panels.splice(index, 1);
      if (removed) URL.revokeObjectURL(removed.url);
      set({ panels });
    },

    analyse: async ({ profiles, lang }) => {
      const { panels } = get();
      const signal = startRequest();
      set({ status: "analysing", error: null, corrections: [], isDemo: false, changedVerdicts: [], attemptProfiles: profiles });
      try {
        const result = await api.scan(
          { images: panels.map((panel) => panel.file), profiles, lang, panelHints: panels.map((panel) => panel.hint) },
          { signal },
        );
        if (superseded(signal)) return;
        set({ result, scanProfiles: profiles, status: "done" });
        await persist(get());
      } catch (error) {
        failWith(error, signal);
      }
    },

    cancel: () => {
      inflight?.abort();
      inflight = null;
    },

    recheck: async (lang, profiles) => {
      const { result, corrections } = get();
      const scanProfiles = profiles ?? get().scanProfiles;
      if (!result) return;
      const signal = startRequest();
      set({ status: "rechecking", error: null, recheckError: null });
      try {
        const extraction = applyCorrections({ ...result.extraction, user_corrections: [] }, corrections);
        const next = await api.recheck({ extraction, profiles: scanProfiles, lang }, { signal });
        if (superseded(signal)) return;
        set({ result: next, scanProfiles, status: "done", changedVerdicts: changedVerdicts(result, next) });
        await persist(get());
      } catch (error) {
        if (superseded(signal)) return;
        if (isApiError(error) && error.code === "ABORTED") {
          set({ status: "done" });
          return;
        }
        // The demo label must work with no backend at all (judging insurance): answer from the fixtures.
        if (get().isDemo) {
          const { mockApi } = await import("../api/mock");
          const extraction = applyCorrections({ ...result.extraction, user_corrections: [] }, corrections);
          const next = await mockApi.recheck({ extraction, profiles: scanProfiles, lang }).catch(() => null);
          if (next && !superseded(signal)) {
            set({ result: next, scanProfiles, status: "done", changedVerdicts: changedVerdicts(result, next) });
            return;
          }
        }
        set({ status: "done", recheckError: isApiError(error) ? error : new ApiError("INTERNAL", String(error)) });
      }
    },

    addCorrection: async (correction, lang) => get().addCorrections([correction], lang),

    addCorrections: async (corrections, lang) => {
      if (corrections.length === 0) return;
      set({ corrections: [...get().corrections, ...corrections] });
      await get().recheck(lang);
    },

    checkContradiction: async (contradiction, lang) => {
      const { result, corrections } = get();
      if (!result || !contradiction.key) return;
      const { extraction } = result;
      const checked = [...new Set([...(extraction.checked_contradictions ?? []), contradiction.key])];
      const confirmed = confirmsPrintedNumber(extraction, contradiction);
      set({
        result: {
          ...result,
          extraction: { ...extraction, checked_contradictions: checked },
          contradictions: (result.contradictions ?? []).map((item) => (item.key === contradiction.key ? { ...item, checked: true } : item)),
        },
        corrections: confirmed ? [...corrections, makeCorrection(extraction, confirmed.fieldPath, confirmed.value)] : corrections,
      });
      await persist(get());
      await get().recheck(lang);
    },

    loadDemo: async () => {
      const { fixtureScanResult, fixtureProfiles, sampleLabelUrl } = await import("../api/fixtures");
      const response = await fetch(sampleLabelUrl);
      const file = await response.blob();
      revokeAll(get().panels);
      inflight?.abort();
      set({
        panels: [makePanel(file, "back")],
        result: structuredClone(fixtureScanResult),
        scanProfiles: structuredClone(fixtureProfiles),
        corrections: [],
        status: "done",
        error: null,
        isDemo: true,
        changedVerdicts: [],
      });
      await persist(get());
    },

    hydrate: async () => {
      if (get().hydrated) return;
      try {
        const stored = await idbGet<StoredScan>(LAST_SCAN_KEY);
        if (stored && !get().result) {
          set({
            panels: stored.panels.map(({ file, hint }) => makePanel(file, hint)),
            result: stored.result,
            scanProfiles: stored.scanProfiles,
            corrections: stored.corrections,
            isDemo: stored.isDemo,
            status: "done",
          });
        }
      } catch {
        // No stored scan available (private mode or cleared storage) — start fresh.
      }
      set({ hydrated: true });
    },

    reset: () => {
      inflight?.abort();
      revokeAll(get().panels);
      set({
        panels: [],
        result: null,
        scanProfiles: [],
        status: "idle",
        error: null,
        corrections: [],
        isDemo: false,
        changedVerdicts: [],
      });
      void idbDel(LAST_SCAN_KEY).catch(() => undefined);
    },
  };
});
