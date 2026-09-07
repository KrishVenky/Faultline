// Copies the backend's generated fixture into the frontend's static assets.
// Run before `vite dev`/`vite build` so the visualization is bound to
// whatever scripts/generate_reference_fixture.py last produced, never to a
// hand-copied or stale duplicate.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "faultline", "fixtures", "reference_cascade.json");
const destDir = join(here, "..", "public", "data");
const dest = join(destDir, "reference_cascade.json");

mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log(`synced ${src} -> ${dest}`);
