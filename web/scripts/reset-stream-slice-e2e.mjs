import { rmSync } from "node:fs";
import { resolve } from "node:path";

for (const suffix of ["", "-wal", "-shm"]) {
  rmSync(resolve("../data/e2e-stream-slice.sqlite3" + suffix), { force: true });
}

for (const path of ["test-results-stream-slice", "playwright-report-stream-slice"]) {
  rmSync(resolve(path), { recursive: true, force: true });
}
