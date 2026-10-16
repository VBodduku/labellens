import type { Size } from "./boxMath";

export const MAX_LONG_SIDE = 2000;
export const JPEG_QUALITY = 0.9;

/** Scales a size down (never up) so its long side is at most `maxLongSide`. */
export function fitWithin(width: number, height: number, maxLongSide = MAX_LONG_SIDE): Size {
  const longSide = Math.max(width, height);
  if (longSide <= maxLongSide || longSide <= 0) return { width, height };
  const scale = maxLongSide / longSide;
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

function canvasToJpeg(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Could not encode the photo"))), "image/jpeg", JPEG_QUALITY);
  });
}

function drawToJpeg(source: CanvasImageSource, width: number, height: number): Promise<Blob> {
  const size = fitWithin(width, height);
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  const context = canvas.getContext("2d");
  if (!context) return Promise.reject(new Error("Canvas is not available"));
  context.drawImage(source, 0, 0, size.width, size.height);
  return canvasToJpeg(canvas);
}

/**
 * Prepares a photo for upload: applies EXIF orientation, downsizes to ≤ 2000 px on the long side and
 * re-encodes as JPEG q 0.9. Formats the browser can't decode as a bitmap (e.g. SVG) pass through unchanged.
 */
export async function prepareImage(file: Blob): Promise<Blob> {
  if (file.type === "image/svg+xml") return file;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    return file;
  }
  try {
    return await drawToJpeg(bitmap, bitmap.width, bitmap.height);
  } finally {
    bitmap.close();
  }
}

/** Grabs the current frame of a playing video at full resolution (downsized to ≤ 2000 px) as JPEG. */
export function captureVideoFrame(video: HTMLVideoElement): Promise<Blob> {
  if (!video.videoWidth || !video.videoHeight) return Promise.reject(new Error("The camera has no frame yet"));
  return drawToJpeg(video, video.videoWidth, video.videoHeight);
}
