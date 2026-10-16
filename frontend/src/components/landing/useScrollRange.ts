import { useTransform, type MotionValue } from "motion/react";

/**
 * Maps a scroll-progress window onto an output range, clamped at both ends.
 * Uses a function transform on purpose: Motion hardware-accelerates plain range maps of scroll
 * progress into WAAPI scroll timelines, which do not clamp past the last keyframe (values drift
 * back to their base once the window has passed).
 */
export function useScrollRange(
  progress: MotionValue<number>,
  [from, to]: readonly [number, number],
  [start, end]: readonly [number, number] = [0, 1],
): MotionValue<number> {
  return useTransform(progress, (value) => {
    const t = Math.min(1, Math.max(0, (value - from) / (to - from)));
    return start + (end - start) * t;
  });
}
