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

test("world pulse exposes canonical Living NPC controls", async () => {
  const source = await readFile(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.match(source, /openNpc/);
  assert.match(source, /adjacent_locations/);
  assert.match(source, /driftwood_1/);
  assert.match(source, /action_type:\s*"GIVE"/);
  assert.match(source, /recipient_id:\s*"npc_mira"/);
});
