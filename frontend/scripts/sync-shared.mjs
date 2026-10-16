// Copies the frozen contract, message templates and fixtures from ../shared into src/shared.
// Cross-platform (pure Node). Skips quietly when ../shared is absent (e.g. a frontend-only deploy).
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const sharedRoot = join(frontendRoot, "..", "shared");
const target = join(frontendRoot, "src", "shared");

if (!existsSync(sharedRoot)) {
  console.log("[sync-shared] ../shared not found — keeping the committed copies in src/shared.");
  process.exit(0);
}

const FIXTURE_EXTENSIONS = new Set([".json", ".svg"]);

/** Copies only when the content differs, so unchanged files keep their timestamps (and git stays clean). */
function copy(from, to) {
  if (existsSync(to) && readFileSync(from).equals(readFileSync(to))) return;
  mkdirSync(dirname(to), { recursive: true });
  copyFileSync(from, to);
}

copy(join(sharedRoot, "contract.ts"), join(target, "contract.ts"));
copy(join(sharedRoot, "messages.en.json"), join(target, "messages.en.json"));

const fixturesDir = join(sharedRoot, "fixtures");
const fixtures = readdirSync(fixturesDir).filter((name) => FIXTURE_EXTENSIONS.has(extname(name)));
for (const name of fixtures) {
  copy(join(fixturesDir, name), join(target, "fixtures", name));
}

console.log(`[sync-shared] contract.ts, messages.en.json and ${fixtures.length} fixtures are in sync.`);
