// Renders the fixture label (src/shared/fixtures/sample_label.svg) to public/hero-poster.webp (1000 px)
// and public/hero-poster-500.webp (phones).
// The landing hero shows this raster instead of the live SVG: the SVG's many text runs and blur filter are
// laid out and rasterised on the main thread, which was the largest cost of the first paint on phones.
// Skips quietly (keeping the committed file) when the SVG or sharp is unavailable.
import { existsSync, statSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(root, "src", "shared", "fixtures", "sample_label.svg");
const target = join(root, "public", "hero-poster.webp");
const small = join(root, "public", "hero-poster-500.webp");

if (!existsSync(source)) {
  console.log("[render-poster] fixture SVG not found — keeping public/hero-poster.webp.");
  process.exit(0);
}
const fresh = (file) => existsSync(file) && statSync(file).mtimeMs >= statSync(source).mtimeMs;
if (fresh(target) && fresh(small)) {
  console.log("[render-poster] up to date.");
  process.exit(0);
}

let sharp;
try {
  sharp = (await import("sharp")).default;
} catch {
  console.log("[render-poster] sharp is not installed — keeping public/hero-poster.webp.");
  process.exit(0);
}

for (const [file, width] of [[target, 1000], [small, 500]]) {
  const info = await sharp(source, { density: 96 }).resize(width, Math.round(width * 1.4)).webp({ quality: 82 }).toFile(file);
  console.log(`[render-poster] wrote ${file.split(/[\/]/).pop()} (${info.width}×${info.height}, ${Math.round(info.size / 1024)} kB).`);
}
