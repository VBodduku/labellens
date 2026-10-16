import { describe, expect, it } from "vitest";
import {
  assessFrame,
  glareRatio,
  laplacianVariance,
  meanBrightness,
  measureFrame,
  motionScore,
  nextReadyStep,
  toGray,
} from "./quality";
import { QUALITY_THRESHOLDS } from "./qualityThresholds";

const W = 64;
const H = 48;

function frame(pixel: (x: number, y: number) => number): Uint8Array {
  const gray = new Uint8Array(W * H);
  for (let y = 0; y < H; y += 1) for (let x = 0; x < W; x += 1) gray[y * W + x] = pixel(x, y);
  return gray;
}

const flat = frame(() => 128);
/** Sharp black/white "text-like" stripes. */
const stripes = frame((x) => (Math.floor(x / 2) % 2 === 0 ? 30 : 220));
/** The same stripes smoothed into a gentle ramp (what blur does to edges). */
const soft = frame((x) => 125 + Math.round(10 * Math.sin(x / 6)));

describe("frame metrics", () => {
  it("converts RGBA to luma", () => {
    const rgba = new Uint8ClampedArray([255, 255, 255, 255, 0, 0, 0, 255, 255, 0, 0, 255]);
    const gray = toGray(rgba, 3, 1);
    expect(gray[0]).toBe(255);
    expect(gray[1]).toBe(0);
    expect(gray[2]).toBeGreaterThan(60);
    expect(gray[2]).toBeLessThan(90);
  });

  it("scores sharp edges far above flat or soft frames", () => {
    expect(laplacianVariance(flat, W, H)).toBe(0);
    expect(laplacianVariance(soft, W, H)).toBeLessThan(QUALITY_THRESHOLDS.blurMin);
    expect(laplacianVariance(stripes, W, H)).toBeGreaterThan(QUALITY_THRESHOLDS.blurMin * 10);
  });

  it("measures glare and brightness", () => {
    expect(glareRatio(frame(() => 255))).toBe(1);
    expect(glareRatio(frame((x) => (x < W / 4 ? 250 : 100)))).toBeCloseTo(0.25);
    expect(meanBrightness(frame(() => 40))).toBe(40);
  });

  it("measures motion against the previous frame", () => {
    expect(motionScore(stripes, null)).toBeNull();
    expect(motionScore(stripes, stripes)).toBe(0);
    const shifted = frame((x) => (Math.floor((x + 1) / 2) % 2 === 0 ? 30 : 220));
    expect(motionScore(shifted, stripes)).toBeGreaterThan(QUALITY_THRESHOLDS.motionMax);
  });
});

describe("assessFrame", () => {
  it("passes a sharp, well-lit, steady frame", () => {
    expect(assessFrame(measureFrame(stripes, W, H, stripes), QUALITY_THRESHOLDS)).toEqual([]);
  });

  it("orders issues by coaching priority: light, glare, then sharpness", () => {
    const dark = measureFrame(frame(() => 20), W, H, null);
    expect(assessFrame(dark, QUALITY_THRESHOLDS)).toEqual(["too_dark", "blurry"]);
    const glare = { blur: 900, glare: 0.4, brightness: 200, motion: 1 };
    expect(assessFrame(glare, QUALITY_THRESHOLDS)).toEqual(["glare"]);
  });

  it("treats a moving camera as blurry ('hold steady')", () => {
    expect(assessFrame({ blur: 900, glare: 0, brightness: 150, motion: 30 }, QUALITY_THRESHOLDS)).toEqual(["blurry"]);
  });
});

describe("shutter ready ring", () => {
  it("fills over 700 ms of continuously good frames and never asks to capture", () => {
    let step = nextReadyStep(null, [], 1000);
    expect(step.progress).toBe(0);
    step = nextReadyStep(step.goodSince, [], 1350);
    expect(step.progress).toBeCloseTo(0.5);
    step = nextReadyStep(step.goodSince, [], 1700);
    expect(step.progress).toBe(1);
    step = nextReadyStep(step.goodSince, [], 9000);
    expect(step).toEqual({ goodSince: 1000, progress: 1 });
    expect(step).not.toHaveProperty("shouldCapture");
  });

  it("empties as soon as a frame turns bad", () => {
    const step = nextReadyStep(0, ["blurry"], 650);
    expect(step).toEqual({ goodSince: null, progress: 0 });
    expect(nextReadyStep(step.goodSince, [], 700).progress).toBe(0);
  });
});
