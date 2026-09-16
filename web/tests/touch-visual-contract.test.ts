import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const touchSource = readFileSync(new URL("../src/touchControls.ts", import.meta.url), "utf8");
const touchFeedbackStyles = readFileSync(new URL("../src/touchFeedback.css", import.meta.url), "utf8");
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

test("held touch controls expose durable pressed feedback without changing keyboard dispatch", () => {
  assert.match(touchSource, /import "\.\/touchFeedback\.css"/);
  assert.match(touchSource, /button\.dataset\.pressed = "false"/);
  assert.match(touchSource, /activePointers\.set\(event\.pointerId, control\);\s*syncPressedState\(control\);\s*dispatchKeyboard\("keydown", control\)/);
  assert.match(touchSource, /activePointers\.delete\(event\.pointerId\);\s*syncPressedState\(control\);\s*dispatchKeyboard\("keyup", control\)/);
  assert.match(touchSource, /button\.dataset\.pressed = Array\.from\(activePointers\.values\(\)\)\.includes\(control\) \? "true" : "false"/);
  assert.match(touchFeedbackStyles, /button\[data-pressed="true"\][\s\S]*background:\s*#65d5d9;[\s\S]*box-shadow:[\s\S]*transform:\s*translateY\(1px\);/);
  assert.match(touchFeedbackStyles, /button:focus-visible[\s\S]*outline:\s*3px solid #65d5d9;/);
});

test("390px touch and dialogue surfaces preserve large targets and bounded modal layout", () => {
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*#touch-controls \.touch-action\s*\{[\s\S]*min-height:\s*118px;/);
  assert.match(styles, /\.touch-action-context\s*\{[\s\S]*overflow-wrap:\s*anywhere;/);
  assert.match(styles, /\.touch-action\[data-contextual="true"\][\s\S]*border-bottom:\s*4px solid #65d5d9;/);
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*#dialogue\s*\{[\s\S]*position:\s*fixed;[\s\S]*max-height:\s*calc\(100dvh - 16px - env\(safe-area-inset-bottom\)\);/);
  assert.match(styles, /\.dialogue-actions button\s*\{[\s\S]*min-height:\s*44px;/);
});

test("390px Living World panel stays compact without hiding its actions", () => {
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*#world-pulse\s*\{[\s\S]*gap:\s*6px;[\s\S]*padding:\s*7px 8px 8px;/);
  assert.match(styles, /#world-pulse-events\s*\{[\s\S]*max-height:\s*38px;[\s\S]*overflow-y:\s*auto;[\s\S]*scrollbar-width:\s*thin;/);
  assert.match(styles, /\.world-pulse-actions\s*\{[\s\S]*display:\s*grid;[\s\S]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\);/);
  assert.match(styles, /\.world-pulse-actions button,\s*\.living-npc-actions button\s*\{[\s\S]*min-height:\s*44px;/);
  assert.match(styles, /\.living-npc-actions\s*\{[\s\S]*flex-wrap:\s*nowrap;[\s\S]*overflow-x:\s*auto;[\s\S]*scroll-snap-type:\s*x proximity;/);
  assert.match(styles, /\.living-npc-actions button\s*\{[\s\S]*flex:\s*0 0 auto;[\s\S]*white-space:\s*nowrap;/);
});
