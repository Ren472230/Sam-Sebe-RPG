import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const touchSource = readFileSync(new URL("../src/touchControls.ts", import.meta.url), "utf8");
const feedbackStyles = readFileSync(new URL("../src/touchFeedback.css", import.meta.url), "utf8");

test("interaction hint mirrors the contextual action state used by touch controls", () => {
  assert.match(touchSource, /button\.dataset\.contextual = nextContext === DEFAULT_ACTION_CONTEXT \? "false" : "true"/);
  assert.match(touchSource, /const isContextual = nextContext !== DEFAULT_ACTION_CONTEXT/);
  assert.match(touchSource, /hint\.dataset\.contextual = isContextual \? "true" : "false"/);
  assert.match(touchSource, /hint\.setAttribute\("aria-label", isContextual \? `Доступно действие: \$\{nextContext\}` : "Подсказка управления"\)/);
});

test("interaction hint exposes a polite accessible status surface", () => {
  assert.match(touchSource, /hint\.setAttribute\("role", "status"\)/);
  assert.match(touchSource, /hint\.setAttribute\("aria-live", "polite"\)/);
  assert.match(touchSource, /hint\.setAttribute\("aria-atomic", "true"\)/);
});

test("interaction hint has distinct neutral and contextual visual states", () => {
  assert.match(feedbackStyles, /#interaction-hint\s*\{[\s\S]*border-left:\s*4px solid #65d5d9;/);
  assert.match(feedbackStyles, /#interaction-hint::before\s*\{[\s\S]*content:\s*"Подсказка";/);
  assert.match(feedbackStyles, /#interaction-hint\[data-contextual="true"\]\s*\{[\s\S]*border-left-color:\s*#e13b3f;/);
  assert.match(feedbackStyles, /#interaction-hint\[data-contextual="true"\]::before\s*\{[\s\S]*content:\s*"Действие";/);
  assert.match(feedbackStyles, /@media \(max-width: 700px\)[\s\S]*#interaction-hint\s*\{[\s\S]*overflow-wrap:\s*anywhere;/);
});
