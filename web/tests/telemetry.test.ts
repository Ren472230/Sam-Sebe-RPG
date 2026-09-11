import test from "node:test";
import assert from "node:assert/strict";

import { TELEMETRY_EVENTS, createTelemetry } from "../src/telemetry.ts";

type SentEvent = { event: string; properties: Record<string, unknown> };

function recorder() {
  const sent: SentEvent[] = [];
  return {
    sent,
    send: async (event: string, properties: Record<string, unknown>) => {
      sent.push({ event, properties });
    }
  };
}

test("telemetry is a no-op when configuration is disabled", () => {
  const record = recorder();
  const telemetry = createTelemetry({ send: record.send });

  assert.equal(telemetry.capture("game_started"), false);
  assert.deepEqual(record.sent, []);
});

test("telemetry exposes exactly the approved event whitelist", () => {
  assert.deepEqual(TELEMETRY_EVENTS, [
    "game_started",
    "first_move",
    "first_interaction",
    "npc_dialogue_started",
    "quest_accepted",
    "quest_completed",
    "wait_used",
    "living_world_event_seen",
    "stream_slice_completed",
    "client_error"
  ]);

  const record = recorder();
  const telemetry = createTelemetry({ enabled: true, send: record.send });
  for (const event of TELEMETRY_EVENTS) assert.equal(telemetry.capture(event), true);
  assert.equal(telemetry.capture("player_email_collected"), false);
  assert.equal(record.sent.length, TELEMETRY_EVENTS.length);
});

test("telemetry drops properties outside the privacy whitelist", () => {
  const record = recorder();
  const telemetry = createTelemetry({ enabled: true, send: record.send });

  telemetry.capture("first_interaction", {
    location_id: "village_square",
    npc_id: "npc_oren",
    email: "private@example.test",
    OPENAI_API_KEY: "secret",
    arbitrary: "value"
  });

  assert.deepEqual(record.sent[0]?.properties, {
    location_id: "village_square",
    npc_id: "npc_oren"
  });
});

test("raw dialogue text never reaches a telemetry payload", () => {
  const record = recorder();
  const telemetry = createTelemetry({ enabled: true, send: record.send });

  telemetry.capture("npc_dialogue_started", {
    npc_id: "npc_oren",
    dialogue_provider: "openai",
    text: "Here is the player's full message",
    dialogue_text: "raw dialogue",
    message: "raw dialogue",
    prompt: "raw prompt"
  });

  assert.deepEqual(record.sent[0]?.properties, {
    npc_id: "npc_oren",
    dialogue_provider: "openai"
  });
});

test("dialogue provider is restricted to the safe enum", () => {
  const record = recorder();
  const telemetry = createTelemetry({ enabled: true, send: record.send });

  telemetry.capture("npc_dialogue_started", { dialogue_provider: "custom-proxy" });
  telemetry.capture("npc_dialogue_started", { dialogue_provider: "fallback" });

  assert.deepEqual(record.sent[0]?.properties, {});
  assert.deepEqual(record.sent[1]?.properties, { dialogue_provider: "fallback" });
});

test("captureOnce emits a first-session milestone only once", () => {
  const record = recorder();
  const telemetry = createTelemetry({ enabled: true, send: record.send });

  assert.equal(telemetry.captureOnce("first_move", { location_id: "workshop_yard" }), true);
  assert.equal(telemetry.captureOnce("first_move", { location_id: "village_square" }), false);
  assert.deepEqual(record.sent, [{
    event: "first_move",
    properties: { location_id: "workshop_yard" }
  }]);
});

test("base properties are sanitized and merged into each event", () => {
  const record = recorder();
  const telemetry = createTelemetry({
    enabled: true,
    send: record.send,
    baseProperties: {
      app_version: "0.1.0",
      commit_sha: "7d7ec138",
      mode: "stream",
      viewport_class: "desktop"
    }
  });

  telemetry.capture("game_started", { location_id: "workshop_yard" });
  assert.deepEqual(record.sent[0]?.properties, {
    app_version: "0.1.0",
    commit_sha: "7d7ec138",
    mode: "stream",
    viewport_class: "desktop",
    location_id: "workshop_yard"
  });
});

test("configured PostHog transport sends an anonymous minimal payload", async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  const fakeFetch = async (url: string | URL | Request, init?: RequestInit) => {
    requests.push({ url: String(url), init });
    return new Response(null, { status: 200 });
  };
  const telemetry = createTelemetry({
    enabled: true,
    privacyConfirmed: true,
    apiKey: "test-project-token",
    host: "https://eu.i.posthog.com",
    sessionId: "dev-test-session",
    fetchImpl: fakeFetch
  });

  assert.equal(telemetry.capture("game_started", { mode: "stream", text: "secret" }), true);
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(requests.length, 1);
  assert.equal(requests[0]?.url, "https://eu.i.posthog.com/i/v0/e/");
  assert.equal(requests[0]?.init?.method, "POST");
  assert.equal(requests[0]?.init?.credentials, "omit");
  const body = JSON.parse(String(requests[0]?.init?.body));
  assert.deepEqual(body, {
    api_key: "test-project-token",
    distinct_id: "dev-test-session",
    event: "game_started",
    properties: {
      mode: "stream",
      $process_person_profile: false
    }
  });
});

test("non-HTTPS PostHog hosts are rejected without making a request", () => {
  let attempted = 0;
  const telemetry = createTelemetry({
    enabled: true,
    privacyConfirmed: true,
    apiKey: "test-project-token",
    host: "http://analytics.example.test",
    fetchImpl: async () => {
      attempted += 1;
      return new Response(null, { status: 200 });
    }
  });

  assert.equal(telemetry.capture("game_started"), false);
  assert.equal(attempted, 0);
});

test("network failure is swallowed and cannot reject gameplay code", async () => {
  let attempted = 0;
  const telemetry = createTelemetry({
    enabled: true,
    send: async () => {
      attempted += 1;
      throw new Error("network down");
    }
  });

  assert.doesNotThrow(() => telemetry.capture("wait_used", { location_id: "village_square" }));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(attempted, 1);
});

test("real PostHog transport stays disabled until privacy is explicitly confirmed", () => {
  let attempted = 0;
  const telemetry = createTelemetry({
    enabled: true,
    apiKey: "test-project-token",
    host: "https://eu.i.posthog.com",
    fetchImpl: async () => {
      attempted += 1;
      return new Response(null, { status: 200 });
    }
  });

  assert.equal(telemetry.capture("game_started"), false);
  assert.equal(attempted, 0);
});
