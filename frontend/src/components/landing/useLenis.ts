import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { useEffect } from "react";

/** Smooth wheel scrolling for the landing page only; off for reduced motion. */
export function useLenis(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;
    const lenis = new Lenis({ autoRaf: true, lerp: 0.12 });
    return () => lenis.destroy();
  }, [enabled]);
}
