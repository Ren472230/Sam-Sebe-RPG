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

export type WorldPulseEvent = {
  tick: number;
  actor_id: string;
  event_type: string;
  summary: string;
};

export type WorldPulse = {
  tick: number;
  latest_events: WorldPulseEvent[];
};

export type AdjacentLocation = { id: string; name: string };
export type MiraLivingState = {
  location_id: string | null;
  wood_stock: number;
  work_cycles: number;
  requested_wood: boolean;
};
export type KasparLivingState = {
  location_id: string | null;
  goal: string | null;
  carrying_wood: number;
};
export type DriftwoodState = {
  location_id: string | null;
  owner_actor_id: string | null;
};
export type LivingNpcProjection = {
  tick: number;
  adjacent_locations: AdjacentLocation[];
  nearby_npc_ids: string[];
  mira: MiraLivingState;
  kaspar: KasparLivingState;
  driftwood: DriftwoodState;
};

export type GameSnapshot = {
  world: WorldView;
  quest: QuestState;
  coins: number;
  oren_relation: OrenRelation;
  oren_trust: number;
  world_pulse: WorldPulse;
  living_npc: LivingNpcProjection;
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
  npc_id: string;
  text: string;
  proposal: string | null;
  social_action: string | null;
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
  world_pulse?: unknown;
  living_npc?: unknown;
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
      oren_trust: response.oren_relation.trust,
      world_pulse: mapWorldPulse(response.world_pulse),
      living_npc: mapLivingNpc(response.living_npc)
    };
  }

  action(input: {
    player_id: string;
    action_type: "LOOK" | "MOVE" | "TAKE" | "DROP" | "GIVE" | "WAIT";
    target_id?: string | null;
    recipient_id?: string | null;
    destination_id?: string | null;
    modifiers?: Record<string, unknown> | null;
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

  dialogue(playerId: string, text: string): Promise<DialogueDecision>;
  dialogue(playerId: string, npcId: string, text: string): Promise<DialogueDecision>;
  dialogue(playerId: string, npcOrText: string, maybeText?: string): Promise<DialogueDecision> {
    const body = maybeText === undefined
      ? { player_id: playerId, text: npcOrText }
      : { player_id: playerId, npc_id: npcOrText, text: maybeText };
    return this.request("/api/dialogue", {
      method: "POST",
      body: JSON.stringify(body)
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

function mapWorldPulse(value: unknown): WorldPulse {
  if (!isRecord(value) || typeof value.tick !== "number" || !Array.isArray(value.latest_events)) {
    return { tick: 0, latest_events: [] };
  }
  return {
    tick: value.tick,
    latest_events: value.latest_events.filter(isWorldPulseEvent).map((event) => ({
      tick: event.tick,
      actor_id: event.actor_id,
      event_type: event.event_type,
      summary: event.summary
    }))
  };
}

function mapLivingNpc(value: unknown): LivingNpcProjection {
  const empty: LivingNpcProjection = {
    tick: 0,
    adjacent_locations: [],
    nearby_npc_ids: [],
    mira: { location_id: null, wood_stock: 0, work_cycles: 0, requested_wood: false },
    kaspar: { location_id: null, goal: null, carrying_wood: 0 },
    driftwood: { location_id: null, owner_actor_id: null }
  };
  if (!isRecord(value)) return empty;
  const mira = isRecord(value.mira) ? value.mira : {};
  const kaspar = isRecord(value.kaspar) ? value.kaspar : {};
  const driftwood = isRecord(value.driftwood) ? value.driftwood : {};
  const adjacent = Array.isArray(value.adjacent_locations)
    ? value.adjacent_locations.filter(isAdjacentLocation).map((entry) => ({ id: entry.id, name: entry.name }))
    : [];
  const nearby = Array.isArray(value.nearby_npc_ids)
    ? value.nearby_npc_ids.filter((entry): entry is string => typeof entry === "string")
    : [];
  return {
    tick: typeof value.tick === "number" ? value.tick : 0,
    adjacent_locations: adjacent,
    nearby_npc_ids: nearby,
    mira: {
      location_id: typeof mira.location_id === "string" ? mira.location_id : null,
      wood_stock: typeof mira.wood_stock === "number" ? mira.wood_stock : 0,
      work_cycles: typeof mira.work_cycles === "number" ? mira.work_cycles : 0,
      requested_wood: mira.requested_wood === true
    },
    kaspar: {
      location_id: typeof kaspar.location_id === "string" ? kaspar.location_id : null,
      goal: typeof kaspar.goal === "string" ? kaspar.goal : null,
      carrying_wood: typeof kaspar.carrying_wood === "number" ? kaspar.carrying_wood : 0
    },
    driftwood: {
      location_id: typeof driftwood.location_id === "string" ? driftwood.location_id : null,
      owner_actor_id: typeof driftwood.owner_actor_id === "string" ? driftwood.owner_actor_id : null
    }
  };
}

function isAdjacentLocation(value: unknown): value is AdjacentLocation {
  return isRecord(value) && typeof value.id === "string" && typeof value.name === "string";
}

function isWorldPulseEvent(value: unknown): value is WorldPulseEvent {
  return isRecord(value)
    && typeof value.tick === "number"
    && typeof value.actor_id === "string"
    && typeof value.event_type === "string"
    && typeof value.summary === "string";
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
