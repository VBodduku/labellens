import { describe, expect, it } from "vitest";
import { containSize, cropStyle, focusTransform, projectBox } from "./boxMath";

const natural = { width: 1000, height: 1400 };
const viewport = { width: 390, height: 380 };
const image = containSize(natural, viewport);
/** "Peanuts (22%)" from shared/fixtures/scan_result.json. */
const peanuts = { x: 0.1692, y: 0.2205, w: 0.2184, h: 0.0195 };

describe("containSize", () => {
  it("fits the image inside the viewport keeping its aspect ratio", () => {
    expect(image.height).toBeCloseTo(380);
    expect(image.width).toBeCloseTo(380 / 1.4);
    expect(containSize({ width: 0, height: 10 }, viewport)).toEqual({ width: 0, height: 0 });
  });
});

describe("focusTransform", () => {
  it("centres the box in the viewer and makes it fill ~60%", () => {
    const transform = focusTransform(peanuts, image, viewport);
    const onScreen = projectBox(peanuts, image, viewport, transform);
    expect(onScreen.x + onScreen.width / 2).toBeCloseTo(viewport.width / 2, 0);
    expect(onScreen.y + onScreen.height / 2).toBeCloseTo(viewport.height / 2, 0);
    expect(onScreen.width / viewport.width).toBeCloseTo(0.6, 2);
  });

  it("caps the zoom for tiny boxes", () => {
    const transform = focusTransform({ x: 0.5, y: 0.5, w: 0.001, h: 0.001 }, image, viewport, 0.6, 6);
    expect(transform.scale).toBe(6);
  });

  it("never zooms out below the fitted image for huge boxes", () => {
    const transform = focusTransform({ x: 0, y: 0, w: 1, h: 1 }, image, viewport);
    expect(transform).toEqual({ scale: 1, positionX: 0, positionY: 0 });
  });

  it("clamps so the content never pulls away from the viewer edges", () => {
    const corner = focusTransform({ x: 0, y: 0, w: 0.1, h: 0.02 }, image, viewport);
    expect(corner.positionX).toBeLessThanOrEqual(0);
    expect(corner.positionY).toBe(0);
    expect(corner.positionX).toBeGreaterThanOrEqual(viewport.width * (1 - corner.scale));

    const bottomRight = focusTransform({ x: 0.9, y: 0.98, w: 0.1, h: 0.02 }, image, viewport);
    expect(bottomRight.positionY).toBeCloseTo(viewport.height * (1 - bottomRight.scale));
  });
});

describe("cropStyle", () => {
  it("shows the whole image for a full box", () => {
    expect(cropStyle({ x: 0, y: 0, w: 1, h: 1 }, 0)).toEqual({ backgroundSize: "100% 100%", backgroundPosition: "0% 0%" });
  });

  it("zooms the background in on a small region", () => {
    const style = cropStyle({ x: 0.65, y: 0.8174, w: 0.2188, h: 0.018 });
    const [width] = style.backgroundSize.split(" ");
    expect(parseFloat(width ?? "0")).toBeGreaterThan(300);
  });
});
