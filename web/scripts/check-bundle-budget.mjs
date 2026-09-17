import { readdir, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const MAX_ENTRY_BYTES = 1_200_000;
const assetsDir = fileURLToPath(new URL("../dist/assets/", import.meta.url));
const files = (await readdir(assetsDir)).filter((name) => name.endsWith(".js"));

if (files.length === 0) {
  console.error("Bundle budget: no JavaScript assets found in dist/assets");
  process.exit(1);
}

const measured = await Promise.all(
  files.map(async (name) => ({ name, bytes: (await stat(path.join(assetsDir, name))).size }))
);
measured.sort((a, b) => b.bytes - a.bytes);
const largest = measured[0];

console.log(`Bundle budget: largest JS asset ${largest.name} = ${largest.bytes} bytes; limit = ${MAX_ENTRY_BYTES}`);

if (largest.bytes > MAX_ENTRY_BYTES) {
  console.error(`Bundle budget exceeded by ${largest.bytes - MAX_ENTRY_BYTES} bytes`);
  process.exit(1);
}
