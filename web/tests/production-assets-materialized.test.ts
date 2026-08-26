import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const root = new URL("../public/assets/production/", import.meta.url);

function bytes(path: string): Buffer {
  return readFileSync(new URL(path, root));
}

test("active partial-production WebP derivatives are physically materialized", () => {
  for (const path of [
    "village/L3_ARCHITECTURE_PARTIAL.webp",
    "village/L4_GAMEPLAY_PARTIAL.webp"
  ]) {
    const data = bytes(path);
    assert.ok(data.length > 1000, `${path} must contain real image bytes`);
    assert.equal(data.subarray(0, 4).toString("ascii"), "RIFF");
    assert.equal(data.subarray(8, 12).toString("ascii"), "WEBP");
  }
});

test("PNG provenance derivatives are physically materialized and remain separate from runtime paths", () => {
  const pngSignature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  for (const path of [
    "village/L3_ARCHITECTURE_PARTIAL_SOURCE.png",
    "village/L4_GAMEPLAY_PARTIAL_SOURCE.png"
  ]) {
    const data = bytes(path);
    assert.ok(data.length > 1000, `${path} must contain real image bytes`);
    assert.deepEqual(data.subarray(0, 8), pngSignature);
  }

  const manifest = JSON.parse(bytes("manifest.json").toString("utf8"));
  assert.equal(manifest.village.layers.architecture, "village/L3_ARCHITECTURE_PARTIAL.webp");
  assert.equal(manifest.village.layers.gameplay, "village/L4_GAMEPLAY_PARTIAL.webp");
});
