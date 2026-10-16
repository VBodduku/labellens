import type { Box } from "../shared/contract";

export interface Size {
  width: number;
  height: number;
}

/** react-zoom-pan-pinch state: translate(positionX, positionY) scale(scale), origin top-left. */
export interface ZoomTransform {
  scale: number;
  positionX: number;
  positionY: number;
}

/** Largest size with the image's aspect ratio that fits inside the viewport ("object-fit: contain"). */
export function containSize(natural: Size, viewport: Size): Size {
  if (natural.width <= 0 || natural.height <= 0 || viewport.width <= 0 || viewport.height <= 0) {
    return { width: 0, height: 0 };
  }
  const scale = Math.min(viewport.width / natural.width, viewport.height / natural.height);
  return { width: natural.width * scale, height: natural.height * scale };
}

/** Top-left of the fitted image when centred inside the viewport. */
export function imageOffset(image: Size, viewport: Size): { x: number; y: number } {
  return { x: (viewport.width - image.width) / 2, y: (viewport.height - image.height) / 2 };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Pan/zoom that makes a normalised evidence box fill ~`fill` of the viewer, centred on it.
 * The zoomable content is exactly the viewport's size with the fitted `image` centred inside it, so a
 * content point p lands on screen at `position + p * scale`. Positions are clamped so the content never
 * pulls away from the viewer's edges.
 */
export function focusTransform(box: Box, image: Size, viewport: Size, fill = 0.6, maxScale = 6): ZoomTransform {
  const boxWidth = Math.max(box.w * image.width, 1);
  const boxHeight = Math.max(box.h * image.height, 1);
  const scale = clamp(Math.min((viewport.width * fill) / boxWidth, (viewport.height * fill) / boxHeight), 1, maxScale);
  const offset = imageOffset(image, viewport);
  const centreX = offset.x + (box.x + box.w / 2) * image.width;
  const centreY = offset.y + (box.y + box.h / 2) * image.height;
  return {
    scale,
    positionX: clamp(viewport.width / 2 - centreX * scale, viewport.width * (1 - scale), 0),
    positionY: clamp(viewport.height / 2 - centreY * scale, viewport.height * (1 - scale), 0),
  };
}

/** Where a box lands on screen (relative to the viewer) under a transform. */
export function projectBox(box: Box, image: Size, viewport: Size, transform: ZoomTransform) {
  const offset = imageOffset(image, viewport);
  return {
    x: transform.positionX + (offset.x + box.x * image.width) * transform.scale,
    y: transform.positionY + (offset.y + box.y * image.height) * transform.scale,
    width: box.w * image.width * transform.scale,
    height: box.h * image.height * transform.scale,
  };
}

/** CSS background sizing/position for a thumbnail that shows just `box` (plus padding) of an image. */
export function cropStyle(box: Box, padding = 0.15): { backgroundSize: string; backgroundPosition: string } {
  const padX = box.w * padding;
  const padY = Math.max(box.h * padding * 4, 0.01);
  const x = clamp(box.x - padX, 0, 1);
  const y = clamp(box.y - padY, 0, 1);
  const w = clamp(box.w + padX * 2, 0.01, 1 - x);
  const h = clamp(box.h + padY * 2, 0.01, 1 - y);
  const positionX = w >= 1 ? 0 : (x / (1 - w)) * 100;
  const positionY = h >= 1 ? 0 : (y / (1 - h)) * 100;
  return {
    backgroundSize: `${100 / w}% ${100 / h}%`,
    backgroundPosition: `${positionX}% ${positionY}%`,
  };
}
