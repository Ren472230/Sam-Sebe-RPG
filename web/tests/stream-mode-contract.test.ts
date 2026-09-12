import assert from "node:assert/strict";
import test from "node:test";

import {
  actorDisplayName,
  isStreamMode,
  streamEventLabel,
  streamPhaseLabel
} from "../src/streamMode.ts";


test("stream mode is enabled only by stream=1", () => {
  assert.equal(isStreamMode("?stream=1"), true);
  assert.equal(isStreamMode("?foo=bar&stream=1"), true);
  assert.equal(isStreamMode(""), false);
  assert.equal(isStreamMode("?stream=0"), false);
});


test("stream actor labels include Talen without leaking actor ids", () => {
  assert.equal(actorDisplayName("npc_wayfarer_1", "npc_wayfarer_1"), "Тален");
  assert.equal(actorDisplayName("npc_oren", "Oren"), "Орен");
});


test("stream event labels distinguish the wayfarer and Oren hospitality beat", () => {
  const arrival = streamEventLabel({
    tick: 10,
    actor_id: "npc_wayfarer_1",
    event_type: "WAYFARER_ARRIVED",
    summary: "Talen arrived at The Wayfarer's Hearth with news from the eastern road."
  });
  const bread = streamEventLabel({
    tick: 10,
    actor_id: "npc_oren",
    event_type: "NPC_REQUESTED_RESOURCE",
    summary: "Oren is looking for bread for the newly arrived guest."
  });
  const wood = streamEventLabel({
    tick: 5,
    actor_id: "npc_mira",
    event_type: "NPC_REQUESTED_RESOURCE",
    summary: "Mira requested useful wood for the workshop."
  });

  assert.match(arrival, /Тален|путник/i);
  assert.match(bread, /Орен/i);
  assert.match(bread, /хлеб/i);
  assert.match(wood, /Мира/i);
  assert.match(wood, /древес/i);
});


test("stream labels never expose raw internal payloads", () => {
  const label = streamEventLabel({
    tick: 11,
    actor_id: "npc_unknown",
    event_type: "INTERNAL_ONLY_EVENT",
    summary: '{"source_knowledge_id":12,"trust":99}'
  });

  assert.doesNotMatch(label, /source_knowledge_id/i);
  assert.doesNotMatch(label, /trust\s*:/i);
  assert.doesNotMatch(label, /[{}]/);
  assert.doesNotMatch(label, /npc_unknown/i);
});


test("stream phase label stays audience-readable around the arrival beat", () => {
  assert.match(streamPhaseLabel(0), /вечер|деревн/i);
  assert.match(streamPhaseLabel(9), /деревн|дел/i);
  assert.match(streamPhaseLabel(10), /гост|таверн/i);
});
