// Verifies the performance budget from the frontend spec §12: Three.js and Lenis must never be
// reachable from the entry or the Scan/Result/Profiles/About routes, and the entry stays < 250 kB gzip.
// Reads Vite's build manifest (dist/.vite/manifest.json) and inspects chunk contents.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const dist = join(dirname(fileURLToPath(import.meta.url)), "..", "dist");
const manifestPath = join(dist, ".vite", "manifest.json");
if (!existsSync(manifestPath)) {
  console.error("[check-chunks] dist/.vite/manifest.json not found — run `npm run build` first.");
  process.exit(1);
}

const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const MARKERS = { three: /WebGLRenderer/, lenis: /lenis-smooth/ };
const GUARDED = ["index.html", "src/routes/Scan.tsx", "src/routes/Result.tsx", "src/routes/Profiles.tsx", "src/routes/About.tsx"];
const ENTRY_BUDGET_GZIP = 250 * 1024;

const read = (file) => readFileSync(join(dist, file), "utf8");

/** Static imports only: dynamic imports load on demand and may reach the landing chunks. */
function staticClosure(key, seen = new Set()) {
  if (seen.has(key) || !manifest[key]) return seen;
  seen.add(key);
  for (const child of manifest[key].imports ?? []) staticClosure(child, seen);
  return seen;
}

let failed = false;
for (const entry of GUARDED) {
  if (!manifest[entry]) {
    console.error(`[check-chunks] ${entry} missing from the manifest`);
    failed = true;
    continue;
  }
  const files = [...staticClosure(entry)].map((key) => manifest[key].file);
  const leaks = files.flatMap((file) =>
    Object.entries(MARKERS)
      .filter(([, pattern]) => pattern.test(read(file)))
      .map(([name]) => `${name} in ${file}`),
  );
  if (leaks.length > 0) {
    console.error(`[check-chunks] FAIL ${entry} statically loads ${leaks.join(", ")}`);
    failed = true;
  } else {
    console.log(`[check-chunks] ok   ${entry} (${files.length} chunks, no three/lenis)`);
  }
}

const entryFile = manifest["index.html"]?.file;
if (entryFile) {
  const size = gzipSync(read(entryFile)).length;
  const verdict = size <= ENTRY_BUDGET_GZIP ? "ok  " : "FAIL";
  console.log(`[check-chunks] ${verdict} entry ${entryFile} = ${(size / 1024).toFixed(1)} kB gzip (budget 250 kB)`);
  if (size > ENTRY_BUDGET_GZIP) failed = true;
}

const allFiles = Object.values(manifest).map((chunk) => chunk.file).filter((file) => file.endsWith(".js"));
for (const [name, pattern] of Object.entries(MARKERS)) {
  if (!allFiles.some((file) => pattern.test(read(file)))) {
    console.error(`[check-chunks] FAIL could not find the ${name} chunk at all; update MARKERS`);
    failed = true;
  }
}

process.exit(failed ? 1 : 0);
