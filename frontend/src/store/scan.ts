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
export const COMPARE_SCAN_KEY = "labellens.compareScan";

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

/** The first product of a comparison, set aside while the second one is scanned. */
export interface PinnedScan {
  panels: Panel[];
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
  /** Product A of a comparison (the current scan is product B). */
  pinned: PinnedScan | null;
  pinnedStatus: "idle" | "rechecking";
  pinnedError: ApiError | null;
  /** True after "open product A": the current scan is then A and `pinned` is B (the comparison keeps A first). */
  swapped: boolean;
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
  /** Set the current scan aside as product A and start an empty scan for product B. */
  startCompare: () => Promise<void>;
  stopCompare: () => Promise<void>;
  /** Exchange A and the current scan (to open A's full result). */
  swapCompare: () => Promise<void>;
  /** Engine-only re-evaluation of product A, e.g. for the family product B was checked for. */
  recheckPinned: (profiles: Profile[], lang: Lang) => Promise<void>;
  loadDemo: () => Promise<void>;
  hydrate: () => Promise<void>;
  reset: () => void;
}

let inflight: AbortController | null = null;
let pinnedInflight: AbortController | null = null;

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

async function persistPinned(pinned: PinnedScan | null, swapped: boolean): Promise<void> {
  try {
    if (!pinned) {
      await idbDel(COMPARE_SCAN_KEY);
      return;
    }
    const stored: StoredScan & { swapped: boolean } = {
      panels: pinned.panels.map(({ file, hint }) => ({ file, hint })),
      result: pinned.result,
      scanProfiles: pinned.scanProfiles,
      corrections: pinned.corrections,
      isDemo: pinned.isDemo,
      swapped,
    };
    await idbSet(COMPARE_SCAN_KEY, stored);
  } catch {
    // Storage can be unavailable (private mode, quota); the comparison still works in memory.
  }
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
    pinned: null,
    pinnedStatus: "idle",
    pinnedError: null,
    swapped: false,

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

    startCompare: async () => {
      const { panels, result, scanProfiles, corrections, isDemo } = get();
      if (!result) return;
      inflight?.abort();
      pinnedInflight?.abort();
      const previous = get().pinned;
      if (previous) revokeAll(previous.panels);
      const pinned: PinnedScan = { panels, result, scanProfiles, corrections, isDemo };
      set({
        pinned,
        pinnedStatus: "idle",
        pinnedError: null,
        panels: [],
        result: null,
        corrections: [],
        isDemo: false,
        status: "idle",
        error: null,
        recheckError: null,
        changedVerdicts: [],
        swapped: false,
      });
      await persistPinned(pinned, false);
      await idbDel(LAST_SCAN_KEY).catch(() => undefined);
    },

    stopCompare: async () => {
      pinnedInflight?.abort();
      const { pinned } = get();
      if (pinned) revokeAll(pinned.panels);
      set({ pinned: null, pinnedStatus: "idle", pinnedError: null, swapped: false });
      await persistPinned(null, false);
    },

    swapCompare: async () => {
      const { pinned, panels, result, scanProfiles, corrections, isDemo } = get();
      if (!pinned || !result) return;
      inflight?.abort();
      pinnedInflight?.abort();
      const next: PinnedScan = { panels, result, scanProfiles, corrections, isDemo };
      set({
        ...pinned,
        status: "done",
        error: null,
        recheckError: null,
        changedVerdicts: [],
        pinned: next,
        pinnedStatus: "idle",
        pinnedError: null,
        swapped: !get().swapped,
      });
      await persist(get());
      await persistPinned(next, get().swapped);
    },

    recheckPinned: async (profiles, lang) => {
      const { pinned } = get();
      if (!pinned) return;
      pinnedInflight?.abort();
      const controller = new AbortController();
      pinnedInflight = controller;
      set({ pinnedStatus: "rechecking", pinnedError: null });
      try {
        const extraction = applyCorrections({ ...pinned.result.extraction, user_corrections: [] }, pinned.corrections);
        let next: ScanResult;
        try {
          next = await api.recheck({ extraction, profiles, lang }, { signal: controller.signal });
        } catch (error) {
          // A demo product must compare with no backend at all: answer from the fixtures, as recheck() does.
          if (!pinned.isDemo || (isApiError(error) && error.code === "ABORTED")) throw error;
          const { mockApi } = await import("../api/mock");
          next = await mockApi.recheck({ extraction, profiles, lang });
        }
        if (pinnedInflight !== controller) return;
        const current = get().pinned;
        if (!current) return;
        const updated: PinnedScan = { ...current, result: next, scanProfiles: profiles };
        set({ pinned: updated, pinnedStatus: "idle" });
        await persistPinned(updated, get().swapped);
      } catch (error) {
        if (pinnedInflight !== controller) return;
        if (isApiError(error) && error.code === "ABORTED") {
          set({ pinnedStatus: "idle" });
          return;
        }
        set({ pinnedStatus: "idle", pinnedError: isApiError(error) ? error : new ApiError("INTERNAL", String(error)) });
      }
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
      try {
        const stored = await idbGet<StoredScan & { swapped?: boolean }>(COMPARE_SCAN_KEY);
        if (stored && !get().pinned) {
          const { swapped = false, ...pinned } = stored;
          set({ pinned: { ...pinned, panels: pinned.panels.map(({ file, hint }) => makePanel(file, hint)) }, swapped });
        }
      } catch {
        // No stored comparison available.
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
