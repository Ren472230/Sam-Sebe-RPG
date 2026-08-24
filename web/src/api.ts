export type VisibleActor = {
  actor_id: string;
  name: string;
  actor_type: string;
};

export type VisibleEntity = {
  entity_id: string;
  name: string;
  entity_type: string;
  portable: boolean;
};

export type WorldView = {
  player_id: string;
  location_id: string;
  location_name: string;
  location_description: string;
  visible_actors: VisibleActor[];
  visible_entities: VisibleEntity[];
  inventory: VisibleEntity[];
};

export type QuestState = {
  quest_type: string;
  status: "available" | "active" | "completed";
  required_firewood: number;
  owned_firewood: number;
};

export type GameSnapshot = {
  world: WorldView;
  quest: QuestState;
  coins: number;
  oren_trust: number;
};

export type ActionResult = {
  success: boolean;
  code: string;
  summary: string;
  event_id: number | null;
  replayed: boolean;
};

export type QuestResult = ActionResult & { state: QuestState };

export type DialogueDecision = {
  text: string;
  proposal: string | null;
  used_fallback: boolean;
};

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

export class GameApi {
  async createSession(name = "Ren"): Promise<string> {
    const response = await this.request<{ player_id: string }>("/api/session", {
      method: "POST",
      body: JSON.stringify({ name })
    });
    return response.player_id;
  }

  getState(playerId: string): Promise<GameSnapshot> {
    return this.request(`/api/state/${encodeURIComponent(playerId)}`);
  }

  action(input: {
    player_id: string;
    action_type: "LOOK" | "MOVE" | "TAKE" | "DROP";
    target_id?: string;
    destination_id?: string;
    source_text?: string;
    external_id?: string;
  }): Promise<ActionResult> {
    return this.request("/api/action", {
      method: "POST",
      body: JSON.stringify(input)
    });
  }

  acceptQuest(playerId: string): Promise<QuestResult> {
    return this.request("/api/quest/accept", {
      method: "POST",
      body: JSON.stringify({ player_id: playerId, external_id: requestId("accept") })
    });
  }

  turnInQuest(playerId: string): Promise<QuestResult> {
    return this.request("/api/quest/turn-in", {
      method: "POST",
      body: JSON.stringify({ player_id: playerId, external_id: requestId("turn-in") })
    });
  }

  dialogue(playerId: string, userText: string): Promise<DialogueDecision> {
    return this.request("/api/dialogue", {
      method: "POST",
      body: JSON.stringify({ player_id: playerId, user_text: userText })
    });
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`;
      throw new ApiError(response.status, message);
    }
    return payload as T;
  }
}

export function requestId(prefix: string): string {
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${id}`;
}
