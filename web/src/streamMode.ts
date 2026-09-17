import type { WorldPulseEvent } from "./api";

export function isStreamMode(search: string): boolean {
  return new URLSearchParams(search).get("stream") === "1";
}

export function actorDisplayName(actorId: string, fallback: string): string {
  if (actorId === "npc_mira") return "Мира";
  if (actorId === "npc_kaspar") return "Каспар";
  if (actorId === "npc_oren") return "Орен";
  if (actorId === "npc_wayfarer_1") return "Тален";
  if (actorId.startsWith("npc_")) return "Житель деревни";
  return fallback;
}

export function streamEventLabel(event: WorldPulseEvent): string {
  if (event.event_type === "WAYFARER_ARRIVED" && event.actor_id === "npc_wayfarer_1") {
    return "Тален прибыл в таверну с новостями с дороги";
  }
  if (event.event_type === "NPC_REQUESTED_RESOURCE" && event.actor_id === "npc_oren") {
    return "Орен ищет хлеб для гостя";
  }
  if (event.event_type === "NPC_REQUESTED_RESOURCE" && event.actor_id === "npc_mira") {
    return "Мира просит древесину для мастерской";
  }
  if (event.event_type === "NPC_COLLECTED_RESOURCE" && event.actor_id === "npc_kaspar") {
    return "Каспар подобрал древесину у реки";
  }
  if (event.event_type === "NPC_DELIVERED_RESOURCE" && event.actor_id === "npc_kaspar") {
    return "Каспар принёс древесину Мире";
  }
  if (event.event_type === "NPC_WORKED" && event.actor_id === "npc_mira") {
    return "Мира завершила рабочий цикл";
  }
  if (event.event_type === "NPC_MOVED") {
    return `${actorDisplayName(event.actor_id, "Кто-то")} отправился дальше по своим делам`;
  }
  return "В деревне что-то изменилось";
}

export function streamPhaseLabel(tick: number): string {
  if (tick < 5) return "Вечер начинается — деревня живёт своим ритмом";
  if (tick < 10) return "Деревня в движении — у жителей появляются свои дела";
  return "В таверне появился гость — вечерняя история развивается";
}
