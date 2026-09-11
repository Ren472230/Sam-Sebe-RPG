export const TELEMETRY_EVENTS = [
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
] as const;

export type TelemetryEventName = (typeof TELEMETRY_EVENTS)[number];
export type DialogueProvider = "openai" | "fallback";
export type GameMode = "normal" | "stream";

export type TelemetryProperties = {
  app_version?: string;
  commit_sha?: string;
  mode?: GameMode;
  location_id?: string;
  npc_id?: string;
  quest_id?: string;
  dialogue_provider?: DialogueProvider;
  elapsed_bucket?: string;
  viewport_class?: string;
};

export type TelemetrySender = (
  event: TelemetryEventName,
  properties: Record<string, unknown>
) => void | Promise<void>;

export type TelemetryConfig = {
  enabled?: boolean;
  privacyConfirmed?: boolean;
  apiKey?: string;
  host?: string;
  sessionId?: string;
  baseProperties?: TelemetryProperties;
  send?: TelemetrySender;
  fetchImpl?: typeof fetch;
};

export type Telemetry = {
  capture(event: string, properties?: Record<string, unknown>): boolean;
  captureOnce(event: string, properties?: Record<string, unknown>): boolean;
};

const EVENT_NAMES = new Set<string>(TELEMETRY_EVENTS);
const PROPERTY_NAMES = new Set<keyof TelemetryProperties>([
  "app_version",
  "commit_sha",
  "mode",
  "location_id",
  "npc_id",
  "quest_id",
  "dialogue_provider",
  "elapsed_bucket",
  "viewport_class"
]);
const SAFE_ID = /^[A-Za-z0-9_.:+-]{1,96}$/;
const SAFE_VERSION = /^[A-Za-z0-9_.:+-]{1,96}$/;
const SAFE_BUCKET = /^[A-Za-z0-9_.:+<>=-]{1,32}$/;
const SAFE_VIEWPORT = /^[A-Za-z0-9_.:+-]{1,32}$/;

export function createTelemetry(config: TelemetryConfig = {}): Telemetry {
  const sender = config.enabled ? resolveSender(config) : null;
  const baseProperties = sanitizeProperties(config.baseProperties ?? {});
  const sentOnce = new Set<string>();

  const capture = (event: string, properties: Record<string, unknown> = {}): boolean => {
    if (!sender || !EVENT_NAMES.has(event)) return false;
    const safeProperties = {
      ...baseProperties,
      ...sanitizeProperties(properties)
    };
    try {
      void Promise.resolve(sender(event as TelemetryEventName, safeProperties)).catch(() => undefined);
      return true;
    } catch {
      return false;
    }
  };

  return {
    capture,
    captureOnce(event: string, properties: Record<string, unknown> = {}): boolean {
      if (sentOnce.has(event)) return false;
      const accepted = capture(event, properties);
      if (accepted) sentOnce.add(event);
      return accepted;
    }
  };
}

export function configureTelemetry(config: TelemetryConfig): void {
  currentTelemetry = createTelemetry(config);
}

export function captureTelemetry(
  event: string,
  properties: Record<string, unknown> = {}
): boolean {
  return currentTelemetry.capture(event, properties);
}

export function captureTelemetryOnce(
  event: string,
  properties: Record<string, unknown> = {}
): boolean {
  return currentTelemetry.captureOnce(event, properties);
}

export function viewportClass(width: number): string {
  if (width < 768) return "mobile";
  if (width < 1200) return "tablet";
  return "desktop";
}

let currentTelemetry: Telemetry = createTelemetry();

function resolveSender(config: TelemetryConfig): TelemetrySender | null {
  if (config.send) return config.send;
  if (!config.privacyConfirmed) return null;
  const apiKey = config.apiKey?.trim();
  const host = config.host?.trim();
  const fetchImpl = config.fetchImpl ?? globalThis.fetch;
  if (!apiKey || !host || typeof fetchImpl !== "function") return null;

  let endpoint: string;
  try {
    endpoint = new URL("/i/v0/e/", host).toString();
  } catch {
    return null;
  }
  if (!endpoint.startsWith("https://")) return null;

  const distinctId = safeSessionId(config.sessionId);
  return async (event, properties) => {
    try {
      await fetchImpl(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "omit",
        keepalive: true,
        body: JSON.stringify({
          api_key: apiKey,
          distinct_id: distinctId,
          event,
          properties: {
            ...properties,
            $process_person_profile: false
          }
        })
      });
    } catch {
      // Best-effort by design: analytics can never block gameplay.
    }
  };
}

function sanitizeProperties(input: Record<string, unknown>): Record<string, unknown> {
  const output: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(input)) {
    if (!PROPERTY_NAMES.has(key as keyof TelemetryProperties)) continue;
    if (!isSafeProperty(key as keyof TelemetryProperties, value)) continue;
    output[key] = value;
  }
  return output;
}

function isSafeProperty(key: keyof TelemetryProperties, value: unknown): boolean {
  if (typeof value !== "string") return false;
  if (key === "mode") return value === "normal" || value === "stream";
  if (key === "dialogue_provider") return value === "openai" || value === "fallback";
  if (key === "app_version" || key === "commit_sha") return SAFE_VERSION.test(value);
  if (key === "elapsed_bucket") return SAFE_BUCKET.test(value);
  if (key === "viewport_class") return SAFE_VIEWPORT.test(value);
  return SAFE_ID.test(value);
}

function safeSessionId(configured?: string): string {
  if (configured && SAFE_ID.test(configured)) return configured;
  const random = globalThis.crypto?.randomUUID?.();
  if (random) return `session-${random}`;
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}
