import { GameApi } from "./api";
import {
  clientErrorText,
  postPlaytestEvent,
  type PlaytestClientEventType
} from "./playtestClient";

const SESSION_KEY = "samseberpg.playtest.session";
const STARTED_KEY = "samseberpg.playtest.started";
const sessionId = existingOrNewSessionId();

type PendingEvent = {
  event_type: PlaytestClientEventType;
  success: boolean;
  summary: string;
  evidence?: Record<string, unknown>;
};

let playerId: string | null = null;
let ready = false;
const pending: PendingEvent[] = [];
const originalConsoleError = console.error.bind(console);

document.body.dataset.playtestSession = sessionId;

console.error = (...args: unknown[]): void => {
  record("CONSOLE_ERROR", false, args.map(clientErrorText).join(" "));
  originalConsoleError(...args);
};

window.addEventListener("error", (event) => {
  record("CLIENT_ERROR", false, clientErrorText(event.error ?? event.message), {
    filename: event.filename || undefined,
    line: event.lineno || undefined,
    column: event.colno || undefined
  });
});

window.addEventListener("unhandledrejection", (event) => {
  record("UNHANDLED_REJECTION", false, clientErrorText(event.reason));
});

let lastScene: string | null = null;
let dialogueWasOpen = false;
const observer = new MutationObserver(() => {
  observeScene();
  observeDialogue();
});
observer.observe(document.body, {
  subtree: true,
  childList: true,
  attributes: true,
  attributeFilter: ["data-scene", "hidden"]
});
observeScene();
observeDialogue();

void initialize();

async function initialize(): Promise<void> {
  const api = new GameApi();
  let backendHealthy = false;
  try {
    backendHealthy = await api.health();
    playerId = await api.createSession("Ren");
    const snapshot = await api.getState(playerId);
    await recordSessionBoundary(snapshot.world_pulse.tick, snapshot.world.location_id);
    ready = true;
    await flushPending();

    const firstPlayableFrame = await waitForPlayableFrame(12_000);
    await send({
      event_type: "GAME_BOOT",
      success: backendHealthy && firstPlayableFrame,
      summary: firstPlayableFrame ? "Playable frame rendered" : "Playable frame did not render",
      evidence: {
        backend_healthy: backendHealthy,
        first_playable_frame: firstPlayableFrame,
        scene: document.body.dataset.scene ?? null
      }
    });
  } catch (error) {
    if (playerId !== null && sessionStorage.getItem(STARTED_KEY) !== "1") {
      await safePost({
        event_type: "SESSION_START",
        success: true,
        summary: "Playtest session started before boot failure",
        evidence: { world_tick: 0 }
      });
      sessionStorage.setItem(STARTED_KEY, "1");
    }
    ready = playerId !== null;
    await flushPending();
    if (playerId !== null) {
      await safePost({
        event_type: "GAME_BOOT",
        success: false,
        summary: clientErrorText(error),
        evidence: {
          backend_healthy: backendHealthy,
          first_playable_frame: false
        }
      });
    }
  }
}

async function recordSessionBoundary(worldTick: number, locationId: string): Promise<void> {
  if (sessionStorage.getItem(STARTED_KEY) === "1") {
    await safePost({
      event_type: "PAGE_RELOAD",
      success: true,
      summary: "Page reloaded",
      evidence: { world_tick: worldTick, location_id: locationId }
    });
    return;
  }

  await safePost({
    event_type: "SESSION_START",
    success: true,
    summary: "Autonomous playtest session started",
    evidence: { world_tick: worldTick, location_id: locationId }
  });
  sessionStorage.setItem(STARTED_KEY, "1");
}

function record(
  eventType: PlaytestClientEventType,
  success: boolean,
  summary: string,
  evidence?: Record<string, unknown>
): void {
  const event = { event_type: eventType, success, summary, evidence };
  if (!ready || playerId === null) {
    pending.push(event);
    return;
  }
  void safePost(event);
}

async function flushPending(): Promise<void> {
  if (!ready || playerId === null) return;
  const queued = pending.splice(0, pending.length);
  for (const event of queued) {
    await safePost(event);
  }
}

async function send(event: PendingEvent): Promise<void> {
  if (playerId === null) return;
  await postPlaytestEvent({
    session_id: sessionId,
    player_id: playerId,
    event_type: event.event_type,
    success: event.success,
    summary: event.summary,
    evidence: event.evidence
  });
}

async function safePost(event: PendingEvent): Promise<void> {
  try {
    await send(event);
  } catch {
    // Telemetry must never become a new gameplay failure mode.
  }
}

function observeScene(): void {
  const scene = document.body.dataset.scene;
  if (!scene || scene === lastScene) return;
  lastScene = scene;
  record("SCENE_ENTER", true, `Entered scene ${scene}`, { scene });
}

function observeDialogue(): void {
  const dialogue = document.getElementById("dialogue");
  if (!dialogue) return;
  const open = !dialogue.hidden;
  if (open && !dialogueWasOpen) {
    const heading = dialogue.querySelector("h2")?.textContent?.trim() ?? "";
    record("DIALOGUE_OPEN", true, heading ? `Opened dialogue with ${heading}` : "Opened dialogue", {
      npc_id: heading === "Орен" ? "npc_oren" : null,
      heading
    });
  }
  dialogueWasOpen = open;
}

async function waitForPlayableFrame(timeoutMs: number): Promise<boolean> {
  const started = performance.now();
  while (performance.now() - started < timeoutMs) {
    const canvas = document.querySelector<HTMLCanvasElement>("#game canvas");
    const scene = document.body.dataset.scene;
    if (canvas && canvas.width > 0 && canvas.height > 0 && (scene === "village" || scene === "tavern")) {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      return true;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 50));
  }
  return false;
}

function existingOrNewSessionId(): string {
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const generated = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const value = `playtest-${generated}`;
  sessionStorage.setItem(SESSION_KEY, value);
  return value;
}
