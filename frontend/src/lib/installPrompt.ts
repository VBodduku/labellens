import { useSyncExternalStore } from "react";

/** Chrome/Edge's install event (not in TypeScript's DOM lib). */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export interface InstallState {
  /** Chrome/Edge offered installation (beforeinstallprompt fired and was kept). */
  canPrompt: boolean;
  /** Already running as an installed app. */
  standalone: boolean;
  /** iPhone/iPad: no install prompt exists; show "Share → Add to Home Screen" instead. */
  ios: boolean;
}

let deferred: BeforeInstallPromptEvent | null = null;
let installed = false;
const listeners = new Set<() => void>();
let snapshot: InstallState = { canPrompt: false, standalone: false, ios: false };

export function isIos(userAgent: string, maxTouchPoints: number): boolean {
  return /iPad|iPhone|iPod/.test(userAgent) || (/Macintosh/.test(userAgent) && maxTouchPoints > 1);
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const navigatorWithStandalone = navigator as Navigator & { standalone?: boolean };
  return window.matchMedia?.("(display-mode: standalone)").matches === true || navigatorWithStandalone.standalone === true;
}

function refresh(): void {
  snapshot = {
    canPrompt: deferred !== null && !installed,
    standalone: installed || isStandalone(),
    ios: typeof navigator !== "undefined" && isIos(navigator.userAgent, navigator.maxTouchPoints ?? 0),
  };
  listeners.forEach((listener) => listener());
}

/** Call once at startup, before React renders: the event can fire very early. */
export function captureInstallPrompt(): void {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event as BeforeInstallPromptEvent;
    refresh();
  });
  window.addEventListener("appinstalled", () => {
    installed = true;
    deferred = null;
    refresh();
  });
  refresh();
}

export async function promptInstall(): Promise<boolean> {
  const event = deferred;
  if (!event) return false;
  await event.prompt();
  const choice = await event.userChoice;
  deferred = null;
  installed = choice.outcome === "accepted";
  refresh();
  return installed;
}

export function useInstallState(): InstallState {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => snapshot,
    () => snapshot,
  );
}
