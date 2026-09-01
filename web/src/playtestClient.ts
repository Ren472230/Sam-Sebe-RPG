export type PlaytestClientEventType =
  | "SESSION_START"
  | "GAME_BOOT"
  | "SCENE_ENTER"
  | "DIALOGUE_OPEN"
  | "PAGE_RELOAD"
  | "CLIENT_ERROR"
  | "CONSOLE_ERROR"
  | "UNHANDLED_REJECTION"
  | "SESSION_END";

export type PlaytestClientEvent = {
  session_id: string;
  player_id: string | null;
  event_type: PlaytestClientEventType;
  success: boolean;
  summary: string;
  evidence?: Record<string, unknown>;
};

export async function postPlaytestEvent(
  event: PlaytestClientEvent,
  transport: typeof fetch = fetch
): Promise<number> {
  const response = await transport("/api/playtest/event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(event)
  });
  if (!response.ok) {
    throw new Error(`playtest event rejected: HTTP ${response.status}`);
  }
  const payload = await response.json() as { event_id?: unknown };
  if (typeof payload.event_id !== "number") {
    throw new Error("playtest event response is malformed");
  }
  return payload.event_id;
}

export function clientErrorText(value: unknown): string {
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
