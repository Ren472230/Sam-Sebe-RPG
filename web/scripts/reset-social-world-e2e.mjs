import { rmSync } from "node:fs";
import { resolve } from "node:path";

for (const suffix of ["", "-wal", "-shm"]) {
  rmSync(resolve("../data/e2e-social-world.sqlite3" + suffix), { force: true });
}

for (const path of ["test-results-social-world", "playwright-report-social-world"]) {
  rmSync(resolve(path), { recursive: true, force: true });
}
