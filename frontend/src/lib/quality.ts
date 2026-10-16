import { GLARE_LUMA, GOOD_HOLD_MS, type QualityThresholds } from "./qualityThresholds";

/** Live issues the camera can coach on; motion is reported as `blurry` ("Hold steady"). */
export type LiveIssue = "too_dark" | "glare" | "blurry";

export interface FrameMetrics {
  blur: number;
  glare: number;
  brightness: number;
  /** Mean absolute luma difference from the previous frame; null for the first frame. */
  motion: number | null;
}

/** RGBA bytes → luma (Rec. 601 weights) as one byte per pixel. */
export function toGray(rgba: Uint8ClampedArray | Uint8Array, width: number, height: number): Uint8Array {
  const gray = new Uint8Array(width * height);
  for (let i = 0, p = 0; i < gray.length; i += 1, p += 4) {
    gray[i] = ((rgba[p] ?? 0) * 77 + (rgba[p + 1] ?? 0) * 150 + (rgba[p + 2] ?? 0) * 29) >> 8;
  }
  return gray;
}

/** Variance of the 4-neighbour Laplacian over interior pixels: low = soft edges = blur. */
export function laplacianVariance(gray: Uint8Array, width: number, height: number): number {
  let sum = 0;
  let sumSq = 0;
  let count = 0;
  for (let y = 1; y < height - 1; y += 1) {
    const row = y * width;
    for (let x = 1; x < width - 1; x += 1) {
      const i = row + x;
      const value =
        (gray[i - width] ?? 0) + (gray[i + width] ?? 0) + (gray[i - 1] ?? 0) + (gray[i + 1] ?? 0) - 4 * (gray[i] ?? 0);
      sum += value;
      sumSq += value * value;
      count += 1;
    }
  }
  if (count === 0) return 0;
  const mean = sum / count;
  return sumSq / count - mean * mean;
}

export function glareRatio(gray: Uint8Array): number {
  if (gray.length === 0) return 0;
  let bright = 0;
  for (const value of gray) if (value > GLARE_LUMA) bright += 1;
  return bright / gray.length;
}

export function meanBrightness(gray: Uint8Array): number {
  if (gray.length === 0) return 0;
  let sum = 0;
  for (const value of gray) sum += value;
  return sum / gray.length;
}

export function motionScore(gray: Uint8Array, previous: Uint8Array | null): number | null {
  if (!previous || previous.length !== gray.length || gray.length === 0) return null;
  let sum = 0;
  for (let i = 0; i < gray.length; i += 1) sum += Math.abs((gray[i] ?? 0) - (previous[i] ?? 0));
  return sum / gray.length;
}

export function measureFrame(gray: Uint8Array, width: number, height: number, previous: Uint8Array | null): FrameMetrics {
  return {
    blur: laplacianVariance(gray, width, height),
    glare: glareRatio(gray),
    brightness: meanBrightness(gray),
    motion: motionScore(gray, previous),
  };
}

/** Issues in coaching priority: fix the light first, then glare, then sharpness/steadiness. */
export function assessFrame(metrics: FrameMetrics, thresholds: QualityThresholds): LiveIssue[] {
  const issues: LiveIssue[] = [];
  if (metrics.brightness < thresholds.darkMin) issues.push("too_dark");
  if (metrics.glare > thresholds.glareMax) issues.push("glare");
  const moving = metrics.motion !== null && metrics.motion > thresholds.motionMax;
  if (metrics.blur < thresholds.blurMin || moving) issues.push("blurry");
  return issues;
}

export interface CaptureState {
  /** Timestamp (ms) when the current run of good frames began; null while any check fails. */
  goodSince: number | null;
  captured: boolean;
}

export const INITIAL_CAPTURE_STATE: CaptureState = { goodSince: null, captured: false };

export interface CaptureStep {
  state: CaptureState;
  /** 0..1 fill of the shutter ring. */
  progress: number;
  shouldCapture: boolean;
}

/** Auto-capture once every check has passed continuously for GOOD_HOLD_MS; any bad frame resets the run. */
export function nextCaptureState(state: CaptureState, issues: LiveIssue[], now: number, holdMs = GOOD_HOLD_MS): CaptureStep {
  if (state.captured) return { state, progress: 1, shouldCapture: false };
  if (issues.length > 0) return { state: { goodSince: null, captured: false }, progress: 0, shouldCapture: false };
  const goodSince = state.goodSince ?? now;
  const progress = Math.min(1, (now - goodSince) / holdMs);
  const shouldCapture = progress >= 1;
  return { state: { goodSince, captured: shouldCapture }, progress, shouldCapture };
}
