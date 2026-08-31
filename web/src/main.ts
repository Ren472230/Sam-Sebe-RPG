import Phaser from "phaser";

import { GameApi, requestId, type GameSnapshot, type WorldPulseEvent } from "./api";
import { loadProductionManifest, setProductionManifest } from "./productionArt";
import { setRuntime } from "./runtime";
import { VillageScene } from "./scenes/VillageScene";
import { TavernScene } from "./scenes/TavernScene";
import { ClientState } from "./state";
import { DialoguePanel } from "./ui/DialoguePanel";
import "./styles.css";

async function bootstrap(): Promise<void> {
  const artManifest = await loadProductionManifest();
  setProductionManifest(artManifest);

  const api = new GameApi();
  const playerId = await api.createSession("Ren");
  const state = new ClientState(api, playerId);
  await state.refresh();
  const dialogue = new DialoguePanel(state);
  setRuntime({ api, state, dialogue });
  bindHud(state);
  bindWorldPulse(state);

  const initialScenes = state.snapshot?.world.location_id === "tavern_interior"
    ? [TavernScene, VillageScene]
    : [VillageScene, TavernScene];

  new Phaser.Game({
    type: Phaser.AUTO,
    parent: "game",
    width: 960,
    height: 540,
    backgroundColor: "#24272a",
    scene: initialScenes,
    render: { antialias: true, roundPixels: true }
  });
}

function bindHud(state: ClientState): void {
  const hud = document.getElementById("hud");
  if (!hud) return;
  state.subscribe((snapshot) => {
    document.body.dataset.scene = snapshot.world.location_id === "tavern_interior" ? "tavern" : "village";
    const label = snapshot.quest.status === "available"
      ? "нет активной задачи"
      : snapshot.quest.status === "active"
        ? `дрова ${snapshot.quest.owned_firewood}/${snapshot.quest.required_firewood}`
        : "дрова доставлены ✓";
    hud.textContent = `${snapshot.world.location_name}  ·  ${label}  ·  монеты ${snapshot.coins}  ·  доверие Орена ${snapshot.oren_trust}`;
  });
}

function bindWorldPulse(state: ClientState): void {
  const root = document.getElementById("world-pulse");
  const tick = document.getElementById("world-pulse-tick");
  const nearby = document.getElementById("world-pulse-nearby");
  const events = document.getElementById("world-pulse-events");
  if (!root || !tick || !nearby || !events) return;

  const buttons = Array.from(root.querySelectorAll<HTMLButtonElement>("button[data-wait-ticks]"));
  let waiting = false;

  const setWaiting = (value: boolean): void => {
    waiting = value;
    for (const button of buttons) button.disabled = value;
    root.dataset.waiting = value ? "true" : "false";
  };

  const render = (snapshot: GameSnapshot): void => {
    tick.textContent = `Шаг ${snapshot.world_pulse.tick}`;
    const names = snapshot.world.visible_actors
      .filter((actor) => actor.actor_type === "npc")
      .map((actor) => actorName(actor.actor_id, actor.name));
    nearby.textContent = names.length > 0 ? `Рядом: ${names.join(", ")}` : "Рядом: никого";

    events.replaceChildren();
    const recent = snapshot.world_pulse.latest_events.slice(-3).reverse();
    if (recent.length === 0) {
      const item = document.createElement("li");
      item.textContent = "Мир пока тих.";
      events.append(item);
      return;
    }
    for (const event of recent) {
      const item = document.createElement("li");
      item.textContent = eventText(event);
      events.append(item);
    }
  };

  state.subscribe(render);

  for (const button of buttons) {
    button.addEventListener("click", async () => {
      if (waiting) return;
      const ticks = Number(button.dataset.waitTicks);
      if (!Number.isInteger(ticks) || ticks < 1) return;
      setWaiting(true);
      try {
        const result = await state.api.action({
          player_id: state.playerId,
          action_type: "WAIT",
          modifiers: { ticks },
          external_id: requestId(`wait-${ticks}`)
        });
        if (!result.success) throw new Error(result.summary);
        await state.refresh();
      } catch (error) {
        events.replaceChildren();
        const item = document.createElement("li");
        item.textContent = error instanceof Error ? error.message : "Не удалось продвинуть время мира";
        events.append(item);
      } finally {
        setWaiting(false);
      }
    });
  }
}

function actorName(actorId: string, fallback: string): string {
  if (actorId === "npc_mira") return "Мира";
  if (actorId === "npc_kaspar") return "Каспар";
  if (actorId === "npc_oren") return "Орен";
  return fallback;
}

function eventText(event: WorldPulseEvent): string {
  if (event.event_type === "NPC_REQUESTED_RESOURCE") return "Мира просит древесину";
  if (event.event_type === "NPC_COLLECTED_RESOURCE") return "Каспар подобрал древесину";
  if (event.event_type === "NPC_DELIVERED_RESOURCE") return "Каспар принёс древесину Мире";
  if (event.event_type === "NPC_WORKED") return "Мира завершила рабочий цикл";
  if (event.event_type === "NPC_MOVED") return `${actorName(event.actor_id, event.actor_id)} отправился дальше по своим делам`;
  return `${actorName(event.actor_id, event.actor_id)}: ${event.summary}`;
}

bootstrap().catch((error) => {
  const root = document.getElementById("game");
  if (root) {
    root.textContent = `Не удалось запустить игру: ${error instanceof Error ? error.message : "неизвестная ошибка"}`;
  }
});
