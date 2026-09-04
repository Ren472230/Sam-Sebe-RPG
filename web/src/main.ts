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
  bindWorldPulse(state, dialogue);

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

function bindWorldPulse(state: ClientState, dialogue: DialoguePanel): void {
  const root = document.getElementById("world-pulse");
  const tick = document.getElementById("world-pulse-tick");
  const nearby = document.getElementById("world-pulse-nearby");
  const events = document.getElementById("world-pulse-events");
  if (!root || !tick || !nearby || !events) return;

  const waitButtons = Array.from(root.querySelectorAll<HTMLButtonElement>("button[data-wait-ticks]"));
  const livingActions = document.createElement("div");
  livingActions.className = "living-npc-actions";
  livingActions.setAttribute("aria-label", "Действия живого мира");
  root.append(livingActions);
  let busy = false;

  const setBusy = (value: boolean): void => {
    busy = value;
    for (const button of waitButtons) button.disabled = value;
    for (const button of livingActions.querySelectorAll<HTMLButtonElement>("button")) {
      button.disabled = value;
    }
    root.dataset.waiting = value ? "true" : "false";
  };

  const showError = (error: unknown): void => {
    events.replaceChildren();
    const item = document.createElement("li");
    item.textContent = error instanceof Error ? error.message : "Действие мира не удалось";
    events.append(item);
  };

  const runAction = async (input: Parameters<GameApi["action"]>[0]): Promise<void> => {
    if (busy) return;
    setBusy(true);
    try {
      const result = await state.api.action(input);
      if (!result.success) throw new Error(result.summary);
      await state.refresh();
    } catch (error) {
      showError(error);
    } finally {
      setBusy(false);
    }
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
    } else {
      for (const event of recent) {
        const item = document.createElement("li");
        item.textContent = eventText(event);
        events.append(item);
      }
    }

    livingActions.replaceChildren();
    for (const npcId of snapshot.living_npc.nearby_npc_ids) {
      livingActions.append(actionButton(`Поговорить: ${actorName(npcId, npcId)}`, () => {
        void dialogue.openNpc(npcId);
      }));
    }
    for (const destination of snapshot.living_npc.adjacent_locations) {
      livingActions.append(actionButton(`Идти: ${locationName(destination.id, destination.name)}`, () => {
        void runAction({
          player_id: state.playerId,
          action_type: "MOVE",
          destination_id: destination.id,
          external_id: requestId(`living-move-${destination.id}`)
        });
      }));
    }

    const driftwood = snapshot.living_npc.driftwood;
    if (
      snapshot.world.location_id === "river_edge"
      && driftwood.location_id === "river_edge"
      && !driftwood.owner_actor_id
    ) {
      livingActions.append(actionButton("Подобрать корягу", () => {
        void runAction({
          player_id: state.playerId,
          action_type: "TAKE",
          target_id: "driftwood_1",
          external_id: requestId("living-take-driftwood")
        });
      }));
    }

    if (
      snapshot.world.location_id === snapshot.living_npc.mira.location_id
      && driftwood.owner_actor_id === state.playerId
      && snapshot.living_npc.mira.requested_wood
    ) {
      livingActions.append(actionButton("Отдать корягу Мире", () => {
        void runAction({
          player_id: state.playerId,
          action_type: "GIVE",
          target_id: "driftwood_1",
          recipient_id: "npc_mira",
          external_id: requestId("living-give-driftwood")
        });
      }));
    }
  };

  state.subscribe(render);

  for (const button of waitButtons) {
    button.addEventListener("click", () => {
      const ticks = Number(button.dataset.waitTicks);
      if (!Number.isInteger(ticks) || ticks < 1) return;
      void runAction({
        player_id: state.playerId,
        action_type: "WAIT",
        modifiers: { ticks },
        external_id: requestId(`wait-${ticks}`)
      });
    });
  }
}

function actionButton(label: string, onClick: () => void): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function actorName(actorId: string, fallback: string): string {
  if (actorId === "npc_mira") return "Мира";
  if (actorId === "npc_kaspar") return "Каспар";
  if (actorId === "npc_oren") return "Орен";
  return fallback;
}

function locationName(locationId: string, fallback: string): string {
  if (locationId === "workshop_yard") return "мастерская";
  if (locationId === "village_square") return "площадь";
  if (locationId === "river_edge") return "река";
  if (locationId === "tavern_interior") return "таверна";
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
