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

export type OrenRelation = {
  familiarity: number;
  trust: number;
  affinity: number;
  fear: number;
  conflict: number;
  romance: number;
};

export type GameSnapshot = {
  world: WorldView;
  quest: QuestState;
  coins: number;
  oren_relation: OrenRelation;
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

type CanonicalLocation = { id: string; name: string; description: string };
type CanonicalActor = Partial<VisibleActor> & { id?: string };
type CanonicalEntity = Partial<VisibleEntity> & { id?: string };
type FrozenStateResponse = {
  player_id: string;
  location: CanonicalLocation;
  visible_actors: CanonicalActor[];
  visible_entities: CanonicalEntity[];
  inventory: CanonicalEntity[];
  quest: QuestState;
  coins: number;
  oren_relation: OrenRelation;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class GameApi {
  async health(): Promise<boolean> {
    const response = await this.request<{ ok: boolean }>("/api/health");
    return response.ok;
  }

  async createSession(name = "Player", externalId = "local-player"): Promise<string> {
    const response = await this.request<{ player_id: string }>("/api/session", {
      method: "POST",
      body: JSON.stringify({ external_id: externalId, name })
    });
    return response.player_id;
  }

  async getState(playerId: string): Promise<GameSnapshot> {
    const response = await this.request<unknown>(`/api/state/${encodeURIComponent(playerId)}`);
    if (!isFrozenStateResponse(response)) {
      throw new ApiError(200, "Некорректный ответ backend: состояние имеет неожиданный формат.");
    }
    return {
      world: {
        player_id: response.player_id,
        location_id: response.location.id,
        location_name: response.location.name,
        location_description: response.location.description,
        visible_actors: response.visible_actors.map(mapActor),
        visible_entities: response.visible_entities.map(mapEntity),
        inventory: response.inventory.map(mapEntity)
      },
      quest: response.quest,
      coins: response.coins,
      oren_relation: response.oren_relation,
      oren_trust: response.oren_relation.trust
    };
  }

  action(input: {
    player_id: string;
    action_type: "LOOK" | "MOVE" | "TAKE" | "DROP" | "GIVE" | "WAIT";
    target_id?: string | null;
    recipient_id?: string | null;
    destination_id?: string | null;
    modifiers?: { ticks?: number } | null;
    external_id?: string;
  }): Promise<ActionResult> {
    return this.request("/api/action", {
      method: "POST",
      body: JSON.stringify({
        player_id: input.player_id,
        action_type: input.action_type,
        target_id: input.target_id ?? null,
        recipient_id: input.recipient_id ?? null,
        destination_id: input.destination_id ?? null,
        modifiers: input.modifiers ?? null,
        external_id: input.external_id ?? requestId(input.action_type.toLowerCase())
      })
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

  dialogue(playerId: string, text: string): Promise<DialogueDecision> {
    return this.request("/api/dialogue", {
      method: "POST",
      body: JSON.stringify({ player_id: playerId, text })
    });
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await fetch(path, {
        ...init,
        headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
      });
    } catch (error) {
      const detail = error instanceof Error ? ` ${error.message}` : "";
      throw new ApiError(0, `Backend недоступен. Запусти Python server и обнови страницу.${detail}`);
    }

    const payload = await response.json().catch(() => ({} as Record<string, unknown>));
    if (!response.ok) {
      const detail = (payload as { detail?: unknown }).detail;
      const message = typeof detail === "string" ? detail : `HTTP ${response.status}`;
      throw new ApiError(response.status, message);
    }
    return payload as T;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isFrozenStateResponse(value: unknown): value is FrozenStateResponse {
  if (!isRecord(value)) return false;
  const location = value.location;
  const quest = value.quest;
  const relation = value.oren_relation;
  if (!isRecord(location) || !isRecord(quest) || !isRecord(relation)) return false;

  return typeof value.player_id === "string"
    && typeof location.id === "string"
    && typeof location.name === "string"
    && typeof location.description === "string"
    && Array.isArray(value.visible_actors)
    && value.visible_actors.every(isRecord)
    && Array.isArray(value.visible_entities)
    && value.visible_entities.every(isRecord)
    && Array.isArray(value.inventory)
    && value.inventory.every(isRecord)
    && typeof quest.quest_type === "string"
    && (quest.status === "available" || quest.status === "active" || quest.status === "completed")
    && typeof quest.required_firewood === "number"
    && typeof quest.owned_firewood === "number"
    && typeof value.coins === "number"
    && typeof relation.trust === "number";
}

function mapActor(actor: CanonicalActor): VisibleActor {
  return {
    actor_id: actor.actor_id ?? actor.id ?? "unknown-actor",
    name: actor.name ?? "Unknown actor",
    actor_type: actor.actor_type ?? "npc"
  };
}

function mapEntity(entity: CanonicalEntity): VisibleEntity {
  return {
    entity_id: entity.entity_id ?? entity.id ?? "unknown-entity",
    name: entity.name ?? "Unknown entity",
    entity_type: entity.entity_type ?? "unknown",
    portable: entity.portable ?? false
  };
}

export function requestId(prefix: string): string {
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${id}`;
}
