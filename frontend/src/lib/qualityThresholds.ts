/**
 * Live camera quality thresholds — the single place to tune them. Calibrate on the demo phone with the
 * `?debug=1` overlay on the Scan route (it prints the live values next to these limits).
 */
export const QUALITY_THRESHOLDS = {
  /** Minimum variance of the 3×3 Laplacian on the 320 px grayscale frame; below = blurry. */
  blurMin: 110,
  /** Maximum fraction of pixels with luma > 245; above = glare. */
  glareMax: 0.05,
  /** Minimum mean luma (0–255); below = too dark. */
  darkMin: 70,
  /** Maximum mean absolute luma difference vs the previous frame; above = moving. */
  motionMax: 7,
} as const;

export type QualityThresholds = { [K in keyof typeof QUALITY_THRESHOLDS]: number };

/** How long every check must pass continuously before auto-capture fires. */
export const GOOD_HOLD_MS = 700;
/** Frames analysed per second. */
export const SAMPLE_FPS = 7;
/** Width of the analysed frame in pixels (height follows the video aspect). */
export const FRAME_WIDTH = 320;
/** Luma above which a pixel counts as glare. */
export const GLARE_LUMA = 245;
