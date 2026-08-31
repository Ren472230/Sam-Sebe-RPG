import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, GameApi } from "../src/api.ts";

test("createSession sends frozen session contract", async () => {
  const originalFetch = globalThis.fetch;
  let capturedBody = "";
  globalThis.fetch = async (_input, init) => {
    capturedBody = String(init?.body ?? "");
    return new Response(JSON.stringify({ player_id: "player_1" }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    const playerId = await new GameApi().createSession("Player");
    assert.equal(playerId, "player_1");
    assert.deepEqual(JSON.parse(capturedBody), { external_id: "local-player", name: "Player" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("getState maps frozen top-level state into client projection", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    player_id: "player_1",
    location: { id: "workshop_yard", name: "Workshop Yard", description: "yard" },
    visible_actors: [{ actor_id: "npc_mira", name: "Mira", actor_type: "npc" }],
    visible_entities: [{ entity_id: "firewood_1", name: "Firewood", entity_type: "firewood", portable: true }],
    inventory: [],
    quest: { quest_type: "bring_5_firewood", status: "available", required_firewood: 5, owned_firewood: 0 },
    coins: 10,
    oren_relation: { familiarity: 0, trust: 3, affinity: 0, fear: 0, conflict: 0, romance: 0 }
  }), { status: 200, headers: { "content-type": "application/json" } });
  try {
    const snapshot = await new GameApi().getState("player_1");
    assert.equal(snapshot.world.location_id, "workshop_yard");
    assert.equal(snapshot.world.visible_entities[0]?.entity_id, "firewood_1");
    assert.equal(snapshot.oren_trust, 3);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("dialogue sends text field from frozen contract", async () => {
  const originalFetch = globalThis.fetch;
  let capturedBody = "";
  globalThis.fetch = async (_input, init) => {
    capturedBody = String(init?.body ?? "");
    return new Response(JSON.stringify({ text: "Принеси дрова.", proposal: "offer_quest:bring_5_firewood", used_fallback: true }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    await new GameApi().dialogue("player_1", "Есть работа?");
    assert.deepEqual(JSON.parse(capturedBody), { player_id: "player_1", text: "Есть работа?" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("network failure becomes readable ApiError", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new TypeError("fetch failed"); };
  try {
    await assert.rejects(() => new GameApi().getState("player_1"), (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 0);
      assert.match(error.message, /Backend/);
      return true;
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("malformed state response becomes readable ApiError", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({}), {
    status: 200,
    headers: { "content-type": "application/json" }
  });
  try {
    await assert.rejects(() => new GameApi().getState("player_1"), (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 200);
      assert.match(error.message, /Некорректный ответ backend/);
      return true;
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("getState maps world pulse into the client snapshot", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    player_id: "player_1",
    location: { id: "workshop_yard", name: "Workshop Yard", description: "yard" },
    visible_actors: [{ actor_id: "npc_mira", name: "Mira", actor_type: "npc" }],
    visible_entities: [],
    inventory: [],
    quest: { quest_type: "bring_5_firewood", status: "available", required_firewood: 5, owned_firewood: 0 },
    coins: 10,
    oren_relation: { familiarity: 0, trust: 0, affinity: 0, fear: 0, conflict: 0, romance: 0 },
    world_pulse: {
      tick: 5,
      latest_events: [
        { tick: 5, actor_id: "npc_mira", event_type: "NPC_REQUESTED_RESOURCE", summary: "Mira requested useful wood." }
      ]
    }
  }), { status: 200, headers: { "content-type": "application/json" } });
  try {
    const snapshot = await new GameApi().getState("player_1");
    assert.equal(snapshot.world_pulse.tick, 5);
    assert.equal(snapshot.world_pulse.latest_events[0]?.event_type, "NPC_REQUESTED_RESOURCE");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("action forwards WAIT ticks to the backend", async () => {
  const originalFetch = globalThis.fetch;
  let capturedBody = "";
  globalThis.fetch = async (_input, init) => {
    capturedBody = String(init?.body ?? "");
    return new Response(JSON.stringify({
      success: true,
      code: "OK",
      summary: "Waited 5 simulation tick(s).",
      event_id: 1,
      replayed: false
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    await new GameApi().action({
      player_id: "player_1",
      action_type: "WAIT",
      modifiers: { ticks: 5 },
      external_id: "wait-five"
    });
    const body = JSON.parse(capturedBody);
    assert.equal(body.action_type, "WAIT");
    assert.deepEqual(body.modifiers, { ticks: 5 });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
