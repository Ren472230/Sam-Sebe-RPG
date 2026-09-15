import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const touchSource = readFileSync(new URL("../src/touchControls.ts", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

test("touch action control mirrors the existing interaction hint without changing E semantics", () => {
  assert.match(touchSource, /button\.dataset\.touchKey = "E"/);
  assert.match(touchSource, /button\.setAttribute\("aria-label", "Взаимодействовать"\)/);
  assert.match(touchSource, /className = "touch-action-key"/);
  assert.match(touchSource, /className = "touch-action-context"/);
  assert.match(touchSource, /const TOUCH_ACTION_PREFIX = "Действие – "/);
  assert.match(touchSource, /new MutationObserver\(sync\)\.observe\(hint/);
  assert.match(touchSource, /button\.dataset\.contextual = nextContext === DEFAULT_ACTION_CONTEXT \? "false" : "true"/);
});

test("390px touch and dialogue surfaces preserve large targets and bounded modal layout", () => {
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*#touch-controls \.touch-action\s*\{[\s\S]*min-height:\s*118px;/);
  assert.match(styles, /\.touch-action-context\s*\{[\s\S]*overflow-wrap:\s*anywhere;/);
  assert.match(styles, /\.touch-action\[data-contextual="true"\][\s\S]*border-bottom:\s*4px solid #65d5d9;/);
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*#dialogue\s*\{[\s\S]*position:\s*fixed;[\s\S]*max-height:\s*calc\(100dvh - 16px - env\(safe-area-inset-bottom\)\);/);
  assert.match(styles, /\.dialogue-actions button\s*\{[\s\S]*min-height:\s*44px;/);
});
