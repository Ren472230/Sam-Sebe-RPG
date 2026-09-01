import assert from "node:assert/strict";
import test from "node:test";

import { clientErrorText, postPlaytestEvent } from "../src/playtestClient.ts";


test("postPlaytestEvent sends the narrow client event contract", async () => {
  let capturedPath = "";
  let capturedBody = "";
  const transport: typeof fetch = async (input, init) => {
    capturedPath = String(input);
    capturedBody = String(init?.body ?? "");
    return new Response(JSON.stringify({ event_id: 17 }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  };

  const eventId = await postPlaytestEvent({
    session_id: "session-1",
    player_id: "player-1",
    event_type: "GAME_BOOT",
    success: true,
    summary: "Playable frame rendered",
    evidence: { first_playable_frame: true }
  }, transport);

  assert.equal(eventId, 17);
  assert.equal(capturedPath, "/api/playtest/event");
  assert.deepEqual(JSON.parse(capturedBody), {
    session_id: "session-1",
    player_id: "player-1",
    event_type: "GAME_BOOT",
    success: true,
    summary: "Playable frame rendered",
    evidence: { first_playable_frame: true }
  });
});


test("postPlaytestEvent rejects malformed server responses", async () => {
  const transport: typeof fetch = async () => new Response(JSON.stringify({}), {
    status: 200,
    headers: { "content-type": "application/json" }
  });

  await assert.rejects(
    () => postPlaytestEvent({
      session_id: "session-1",
      player_id: "player-1",
      event_type: "SESSION_START",
      success: true,
      summary: "start"
    }, transport),
    /malformed/
  );
});


test("clientErrorText produces stable readable diagnostics", () => {
  assert.equal(clientErrorText(new TypeError("boom")), "TypeError: boom");
  assert.equal(clientErrorText("plain failure"), "plain failure");
  assert.equal(clientErrorText({ code: "E_TEST" }), '{"code":"E_TEST"}');
});
