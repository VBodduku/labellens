import { motion, useInView, type MotionValue } from "motion/react";
import { lazy, Suspense, useCallback, useLayoutEffect, useRef, useState } from "react";
import { hasWebGL } from "../../lib/featureDetect";
import { HeroChips } from "./HeroChips";
import { HeroPoster } from "./HeroPoster";
import { LABEL_ASPECT } from "./heroChipData";
import { useScrollRange } from "./useScrollRange";

const Hero3D = lazy(() => import("./Hero3D"));

/** Share of the stage the label face may use; the rest is room for chips that float off the edges. */
const MAX_HEIGHT_SHARE = 0.8;
const MAX_WIDTH_SHARE = 0.62;

interface Size {
  width: number;
  height: number;
}

/**
 * Lays out one label rectangle shared by every layer — the 3D packet's face (via its camera), the
 * static poster, the dimming veil and the evidence chips — so highlights land on the exact words.
 */
export function HeroStage({ progress, motionAllowed }: { progress: MotionValue<number>; motionAllowed: boolean }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<Size>({ width: 0, height: 0 });
  const [use3D] = useState(() => motionAllowed && hasWebGL());
  const [ready3D, setReady3D] = useState(false);
  const inView = useInView(stageRef, { margin: "120px" });
  const veil = useScrollRange(progress, [0.03, 0.2], [0, 0.5]);
  const onReady = useCallback(() => setReady3D(true), []);

  useLayoutEffect(() => {
    const node = stageRef.current;
    if (!node) return;
    const measure = () => setSize({ width: node.clientWidth, height: node.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const labelHeight = Math.min(size.height * MAX_HEIGHT_SHARE, (size.width * MAX_WIDTH_SHARE) / LABEL_ASPECT);
  const labelWidth = labelHeight * LABEL_ASPECT;
  const measured = labelHeight > 0;

  return (
    <div ref={stageRef} className="relative size-full">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 aspect-square w-[min(120%,46rem)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,color-mix(in_srgb,var(--beam)_14%,transparent),color-mix(in_srgb,var(--beam-2)_8%,transparent)_55%,transparent)]"
      />
      {use3D && measured && (
        <Suspense fallback={null}>
          <motion.div className="absolute inset-0" initial={{ opacity: 0 }} animate={{ opacity: ready3D ? 1 : 0 }} transition={{ duration: 0.42 }}>
            <Hero3D heightRatio={labelHeight / size.height} active={inView} onReady={onReady} />
          </motion.div>
        </Suspense>
      )}
      {measured && (
        <div
          className="absolute"
          style={{
            width: labelWidth,
            height: labelHeight,
            left: (size.width - labelWidth) / 2,
            top: (size.height - labelHeight) / 2,
          }}
        >
          <div
            aria-hidden="true"
            className="absolute -bottom-[9%] left-[8%] right-[8%] h-[7%] rounded-[50%] bg-black/45 blur-xl"
          />
          <motion.div
            className="absolute inset-0"
            initial={false}
            animate={{ opacity: ready3D ? 0 : 1 }}
            transition={{ duration: 0.42 }}
          >
            <HeroPoster />
          </motion.div>
          <motion.div aria-hidden="true" style={{ opacity: veil }} className="absolute inset-0 rounded-[6px] bg-bg" />
          <HeroChips progress={progress} />
        </div>
      )}
    </div>
  );
}
