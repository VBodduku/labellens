import { m, type MotionValue, useInView } from "motion/react";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { hasWebGL } from "../../lib/featureDetect";
import { HeroChips } from "./HeroChips";
import { HeroPoster } from "./HeroPoster";
import { LABEL_ASPECT } from "./heroChipData";
import { useScrollRange } from "./useScrollRange";

const Hero3D = lazy(() => import("./Hero3D"));

/** Share of the stage the label face may use; the rest is room for chips that float off the edges. */
const MAX_HEIGHT_SHARE = 0.8;
const MAX_WIDTH_SHARE = 0.62;
/** Any sign of a person: only then is the ~200 kB 3D chunk worth downloading and starting. */
const INTERACTION_EVENTS = ["pointermove", "pointerdown", "touchstart", "wheel", "scroll", "keydown"] as const;

/**
 * The label rectangle, sized in pure CSS from the stage (a size container): height = min(80 % of the stage
 * height, 62 % of its width ÷ aspect), centred. No measuring pass is needed before the poster can paint.
 */
const LABEL_RECT_STYLE = {
  width: `min(${MAX_HEIGHT_SHARE * LABEL_ASPECT * 100}cqh, ${MAX_WIDTH_SHARE * 100}cqw)`,
  height: `min(${MAX_HEIGHT_SHARE * 100}cqh, ${(MAX_WIDTH_SHARE / LABEL_ASPECT) * 100}cqw)`,
};

/** Same formula in pixels, for the 3D camera (fraction of the canvas height the label face fills). */
function labelHeightRatio(width: number, height: number): number {
  if (height <= 0) return MAX_HEIGHT_SHARE;
  return Math.min(height * MAX_HEIGHT_SHARE, (width * MAX_WIDTH_SHARE) / LABEL_ASPECT) / height;
}

/**
 * Lays out one label rectangle shared by every layer — the 3D packet's face (via its camera), the
 * static poster, the dimming veil and the evidence chips — so highlights land on the exact words.
 */
export function HeroStage({ progress, motionAllowed }: { progress: MotionValue<number>; motionAllowed: boolean }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [wants3D, setWants3D] = useState(false);
  const [heightRatio, setHeightRatio] = useState<number | null>(null);
  const [chipsReady, setChipsReady] = useState(false);
  const [ready3D, setReady3D] = useState(false);
  const inView = useInView(stageRef, { margin: "120px" });
  const veil = useScrollRange(progress, [0.03, 0.2], [0, 0.5]);
  const onReady = useCallback(() => setReady3D(true), []);

  // The static poster is identical at first paint, so WebGL waits for the first interaction instead of
  // competing with page load. Even the capability check waits: creating a WebGL context to probe support
  // costs hundreds of milliseconds on a phone.
  useEffect(() => {
    if (!motionAllowed) return;
    const start = () => {
      INTERACTION_EVENTS.forEach((type) => window.removeEventListener(type, start));
      if (hasWebGL()) setWants3D(true);
    };
    INTERACTION_EVENTS.forEach((type) => window.addEventListener(type, start, { passive: true }));
    return () => INTERACTION_EVENTS.forEach((type) => window.removeEventListener(type, start));
  }, [motionAllowed]);

  // The 3D camera needs the stage size in pixels — measured only once 3D is actually starting.
  useEffect(() => {
    const node = stageRef.current;
    if (!wants3D || !node) return;
    const observer = new ResizeObserver(() => setHeightRatio(labelHeightRatio(node.clientWidth, node.clientHeight)));
    observer.observe(node);
    return () => observer.disconnect();
  }, [wants3D]);

  // The chips are invisible until the visitor scrolls, so they mount after first paint, when the browser is idle.
  useEffect(() => {
    const show = () => setChipsReady(true);
    if (typeof window.requestIdleCallback === "function") {
      const handle = window.requestIdleCallback(show, { timeout: 1200 });
      return () => window.cancelIdleCallback(handle);
    }
    const timer = window.setTimeout(show, 300);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div ref={stageRef} className="relative size-full [container-type:size]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 aspect-square w-[min(120%,46rem)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,color-mix(in_srgb,var(--beam)_14%,transparent),color-mix(in_srgb,var(--beam-2)_8%,transparent)_55%,transparent)]"
      />
      {wants3D && heightRatio !== null && (
        <Suspense fallback={null}>
          <m.div className="absolute inset-0" initial={{ opacity: 0 }} animate={{ opacity: ready3D ? 1 : 0 }} transition={{ duration: 0.42 }}>
            <Hero3D heightRatio={heightRatio} active={inView} onReady={onReady} />
          </m.div>
        </Suspense>
      )}
      <div className="absolute inset-0 m-auto" style={LABEL_RECT_STYLE}>
        <div aria-hidden="true" className="absolute -bottom-[9%] left-[8%] right-[8%] h-[7%] rounded-[50%] bg-black/45 blur-xl" />
        <m.div className="absolute inset-0" initial={false} animate={{ opacity: ready3D ? 0 : 1 }} transition={{ duration: 0.42 }}>
          <HeroPoster />
        </m.div>
        <m.div aria-hidden="true" style={{ opacity: veil }} className="absolute inset-0 rounded-[6px] bg-bg" />
        {chipsReady && <HeroChips progress={progress} />}
      </div>
    </div>
  );
}
