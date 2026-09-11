import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { GameApi } from "../src/api.ts";

const baseState = {
  player_id: "player_1",
  location: { id: "workshop_yard", name: "Workshop Yard", description: "yard" },
  visible_actors: [{ actor_id: "npc_mira", name: "Mira", actor_type: "npc" }],
  visible_entities: [],
  inventory: [],
  quest: { quest_type: "bring_5_firewood", status: "available", required_firewood: 5, owned_firewood: 0 },
  coins: 10,
  oren_relation: { familiarity: 0, trust: 0, affinity: 0, fear: 0, conflict: 0, romance: 0 },
  living_npc: {
    tick: 2,
    adjacent_locations: [{ id: "village_square", name: "Village Square" }],
    nearby_npc_ids: ["npc_mira"],
    mira: { location_id: "workshop_yard", wood_stock: 0, work_cycles: 2, requested_wood: true },
    kaspar: { location_id: "river_edge", goal: "collect_wood", carrying_wood: 0 },
    driftwood: { location_id: "river_edge", owner_actor_id: null }
  }
};

test("dialogue sends explicit npc_id", async () => {
  const original = globalThis.fetch;
  let body = "";
  globalThis.fetch = async (_input, init) => {
    body = String(init?.body ?? "");
    return new Response(JSON.stringify({
      npc_id: "npc_mira",
      text: "Привет",
      proposal: null,
      social_action: null,
      used_fallback: false
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    await new GameApi().dialogue("player_1", "npc_mira", "Что случилось?");
    assert.deepEqual(JSON.parse(body), {
      player_id: "player_1",
      npc_id: "npc_mira",
      text: "Что случилось?"
    });
  } finally {
    globalThis.fetch = original;
  }
});

test("legacy two-argument dialogue keeps frozen payload", async () => {
  const original = globalThis.fetch;
  let body = "";
  globalThis.fetch = async (_input, init) => {
    body = String(init?.body ?? "");
    return new Response(JSON.stringify({
      npc_id: "npc_oren",
      text: "Привет",
      proposal: null,
      social_action: null,
      used_fallback: false
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    await new GameApi().dialogue("player_1", "Привет");
    assert.deepEqual(JSON.parse(body), { player_id: "player_1", text: "Привет" });
  } finally {
    globalThis.fetch = original;
  }
});

test("GIVE forwards recipient_id", async () => {
  const original = globalThis.fetch;
  let body = "";
  globalThis.fetch = async (_input, init) => {
    body = String(init?.body ?? "");
    return new Response(JSON.stringify({
      success: true,
      code: "OK",
      summary: "ok",
      event_id: 1,
      replayed: false
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    await new GameApi().action({
      player_id: "player_1",
      action_type: "GIVE",
      target_id: "driftwood_1",
      recipient_id: "npc_mira",
      external_id: "give"
    });
    const payload = JSON.parse(body);
    assert.equal(payload.action_type, "GIVE");
    assert.equal(payload.recipient_id, "npc_mira");
  } finally {
    globalThis.fetch = original;
  }
});

test("getState maps Living NPC projection", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify(baseState), {
    status: 200,
    headers: { "content-type": "application/json" }
  });
  try {
    const state = await new GameApi().getState("player_1");
    assert.equal(state.living_npc.tick, 2);
    assert.equal(state.living_npc.mira.requested_wood, true);
    assert.equal(state.living_npc.adjacent_locations[0]?.id, "village_square");
  } finally {
    globalThis.fetch = original;
  }
});

test("dialogue panel exposes generic NPC free-text interaction", async () => {
  const source = await readFile(new URL("../src/ui/DialoguePanel.ts", import.meta.url), "utf8");
  assert.match(source, /openNpc\(/);
  assert.match(source, /textarea/);
  assert.match(source, /Отправить/);
  assert.match(source, /npcId/);
});

test("opening Oren does not auto-submit text before the player can type", async () => {
  const source = await readFile(new URL("../src/ui/DialoguePanel.ts", import.meta.url), "utf8");
  assert.match(source, /async openOren\(\): Promise<void>/);
  assert.match(source, /await this\.openNpc\("npc_oren"\);/);
  assert.doesNotMatch(source, /Привет\. Есть работа\?/);
});

test("dialogue success emits provider metadata without reply text", async () => {
  const source = await readFile(new URL("../src/ui/DialoguePanel.ts", import.meta.url), "utf8");
  assert.match(source, /samseberpg:dialogue-result/);
  assert.match(source, /dialogueResultEvidence\(this\.npcId,\s*decision\.used_fallback\)/);
  assert.doesNotMatch(source, /detail:\s*\{[^}]*text:/s);
});

test("world pulse keeps canonical world actions but does not offer remote NPC talk buttons", async () => {
  const source = await readFile(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.match(source, /adjacent_locations/);
  assert.match(source, /driftwood_1/);
  assert.match(source, /action_type:\s*"GIVE"/);
  assert.match(source, /recipient_id:\s*"npc_mira"/);
  assert.doesNotMatch(source, /Поговорить:/);
  assert.doesNotMatch(source, /const talkableNpcs = snapshot\.world\.visible_actors\.filter/);
});

test("gameplay keyboard yields to text entry and handles E exactly once without missing quick presses", async () => {
  for (const filename of ["VillageScene.ts", "TavernScene.ts"]) {
    const source = await readFile(new URL(`../src/scenes/${filename}`, import.meta.url), "utf8");
    assert.match(source, /addKeys\("W,A,S,D,E",\s*false\)/, `${filename} must not capture text-entry keys globally`);
    assert.match(source, /isTextEntryActive\(\)/, `${filename} must suspend gameplay keys while typing`);
    assert.match(source, /keyboard\.on\("keydown-E",\s*\(event: KeyboardEvent\)/, `${filename} must react to the actual key edge rather than frame polling`);
    assert.match(source, /event\.repeat\s*\|\|\s*isTextEntryActive\(\)/, `${filename} must ignore OS key repeat and text entry`);
    assert.doesNotMatch(source, /Phaser\.Input\.Keyboard\.JustDown\(this\.keys\.E\)/, `${filename} must not miss quick E presses between frames`);
  }
});

test("village scene materializes and talks only to spatially nearby authoritative NPCs", async () => {
  const source = await readFile(new URL("../src/scenes/VillageScene.ts", import.meta.url), "utf8");
  assert.match(source, /visible_actors/);
  assert.match(source, /renderNearbyNpcs\(/);
  assert.match(source, /renderedNpcIds/);
  assert.match(source, /kind:\s*"npc"/);
  assert.match(source, /nearestNpc\(/);
  assert.match(source, /dialogue\.openNpc\(interaction\.actorId\)/);
  assert.match(source, /поговорить с/);
});

test("tavern materializes authoritative visitors instead of naming invisible NPCs", async () => {
  const source = await readFile(new URL("../src/scenes/TavernScene.ts", import.meta.url), "utf8");
  assert.match(source, /visible_actors/);
  assert.match(source, /npc_wayfarer_1/);
  assert.match(source, /renderVisibleVisitors\(/);
  assert.match(source, /dialogue\.openNpc\(interaction\.actorId\)/);
});
