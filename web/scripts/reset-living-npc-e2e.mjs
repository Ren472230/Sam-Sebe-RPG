import { rmSync } from "node:fs";
import { resolve } from "node:path";

for (const suffix of ["", "-wal", "-shm"]) {
  rmSync(resolve("../data/e2e-living-npc.sqlite3" + suffix), { force: true });
}
