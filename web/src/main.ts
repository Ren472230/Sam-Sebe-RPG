import Phaser from "phaser";

import { GameApi, requestId, type GameSnapshot, type WorldPulseEvent } from "./api";
import { loadProductionManifest, setProductionManifest } from "./productionArt";
import { setRuntime } from "./runtime";
import { VillageScene } from "./scenes/VillageScene";
import { TavernScene } from "./scenes/TavernScene";
import { ClientState } from "./state";
import {
  actorDisplayName,
  isStreamMode,
  streamEventLabel,
  streamPhaseLabel
} from "./streamMode";
import { DialoguePanel } from "./ui/DialoguePanel";
import "./styles.css";

async function bootstrap(): Promise<void> {
  const artManifest = await loadProductionManifest();
  setProductionManifest(artManifest);

  const streamMode = isStreamMode(window.location.search);
  document.body.classList.toggle("stream-mode", streamMode);

  const api = new GameApi();
  const playerId = await api.createSession("Ren");
  const state = new ClientState(api, playerId);
  await state.refresh();
  const dialogue = new DialoguePanel(state);
  setRuntime({ api, state, dialogue });
  bindHud(state, streamMode);
  bindWorldPulse(state, dialogue, streamMode);
  if (streamMode) bindStreamStatus(state);

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

function bindHud(state: ClientState, streamMode: boolean): void {
  const hud = document.getElementById("hud");
  if (!hud) return;
  state.subscribe((snapshot) => {
    document.body.dataset.scene = snapshot.world.location_id === "tavern_interior" ? "tavern" : "village";
    if (streamMode) {
      hud.textContent = `${hudLocationName(snapshot.world.location_id, snapshot.world.location_name)}  ·  шаг ${snapshot.world_pulse.tick}`;
      return;
    }

    const objective = snapshot.quest.status === "available"
      ? "Цель: найди таверну и поговори с Ореном"
      : snapshot.quest.status === "active"
        ? `Цель: собери дрова ${snapshot.quest.owned_firewood}/${snapshot.quest.required_firewood} и вернись к Орену`
        : "Цель: дрова доставлены ✓ · исследуй деревню";
    const trust = snapshot.oren_trust > 0 ? `  ·  доверие Орена ${snapshot.oren_trust}` : "";
    hud.textContent = `${hudLocationName(snapshot.world.location_id, snapshot.world.location_name)}  ·  ${objective}  ·  монеты ${snapshot.coins}${trust}`;
  });
}

function bindStreamStatus(state: ClientState): void {
  const app = document.getElementById("app");
  const pulse = document.getElementById("world-pulse");
  if (!app || !pulse) return;

  const root = document.createElement("section");
  root.id = "stream-status";
  root.setAttribute("aria-live", "polite");

  const heading = document.createElement("div");
  heading.className = "stream-status-heading";
  const title = document.createElement("strong");
  title.textContent = "Сейчас в деревне";
  const phase = document.createElement("span");
  phase.className = "stream-status-phase";
  heading.append(title, phase);

  const location = document.createElement("p");
  location.className = "stream-status-location";
  const activities = document.createElement("ul");
  activities.className = "stream-status-activities";
  const recent = document.createElement("ul");
  recent.className = "stream-status-events";
  root.append(heading, location, activities, recent);
  app.insertBefore(root, pulse);

  state.subscribe((snapshot) => {
    phase.textContent = `Шаг ${snapshot.world_pulse.tick} · ${streamPhaseLabel(snapshot.world_pulse.tick)}`;
    location.textContent = `Место: ${hudLocationName(snapshot.world.location_id, snapshot.world.location_name)}`;

    activities.replaceChildren();
    const nearbyNpcs = snapshot.world.visible_actors.filter((actor) => actor.actor_type === "npc");
    if (nearbyNpcs.length === 0) {
      const item = document.createElement("li");
      item.textContent = "Поблизости сейчас тихо.";
      activities.append(item);
    } else {
      for (const actor of nearbyNpcs) {
        const item = document.createElement("li");
        item.textContent = streamActivityLabel(snapshot, actor.actor_id, actor.name);
        activities.append(item);
      }
    }

    recent.replaceChildren();
    const publicEvents = snapshot.world_pulse.latest_events.slice(-4).reverse();
    if (publicEvents.length === 0) {
      const item = document.createElement("li");
      item.textContent = "Мир пока тих.";
      recent.append(item);
    } else {
      for (const event of publicEvents) {
        const item = document.createElement("li");
        item.textContent = streamEventLabel(event);
        recent.append(item);
      }
    }
  });
}

function streamActivityLabel(snapshot: GameSnapshot, actorId: string, fallback: string): string {
  const name = actorDisplayName(actorId, fallback);
  if (actorId === "npc_mira") {
    return snapshot.living_npc.mira.requested_wood
      ? `${name} ждёт древесину для мастерской`
      : `${name} работает в мастерской`;
  }
  if (actorId === "npc_kaspar") {
    if (snapshot.living_npc.kaspar.carrying_wood > 0) return `${name} несёт найденную древесину`;
    if (snapshot.living_npc.kaspar.goal) return `${name} занят своим делом`;
    return `${name} проверяет окрестности`;
  }
  if (actorId === "npc_oren") return `${name} держит таверну`;
  if (actorId === "npc_wayfarer_1") return `${name} отдыхает после дороги`;
  return `${name} занят своими делами`;
}

function bindWorldPulse(state: ClientState, dialogue: DialoguePanel, streamMode: boolean): void {
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
      .map((actor) => actorDisplayName(actor.actor_id, actor.name));
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
        item.textContent = streamMode ? streamEventLabel(event) : eventText(event);
        events.append(item);
      }
    }

    livingActions.replaceChildren();
    for (const npcId of snapshot.living_npc.nearby_npc_ids) {
      livingActions.append(actionButton(`Поговорить: ${actorDisplayName(npcId, npcId)}`, () => {
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

    const breadVisible = snapshot.world.visible_entities.some(
      (entity) => entity.entity_id === "bread_loaf_1"
    );
    if (snapshot.world.location_id === "village_square" && breadVisible) {
      livingActions.append(actionButton("Подобрать хлеб", () => {
        void runAction({
          player_id: state.playerId,
          action_type: "TAKE",
          target_id: "bread_loaf_1",
          external_id: requestId("living-take-bread")
        });
      }));
    }

    const breadOwned = snapshot.world.inventory.some(
      (entity) => entity.entity_id === "bread_loaf_1"
    );
    const orenNearby = snapshot.living_npc.nearby_npc_ids.includes("npc_oren");
    if (snapshot.world.location_id === "tavern_interior" && breadOwned && orenNearby) {
      livingActions.append(actionButton("Отдать хлеб Орену", () => {
        void runAction({
          player_id: state.playerId,
          action_type: "GIVE",
          target_id: "bread_loaf_1",
          recipient_id: "npc_oren",
          external_id: requestId("living-give-bread")
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

function hudLocationName(locationId: string, fallback: string): string {
  if (locationId === "workshop_yard") return "Мастерская";
  if (locationId === "village_square") return "Площадь";
  if (locationId === "river_edge") return "Берег реки";
  if (locationId === "tavern_interior") return "Таверна";
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
  return streamEventLabel(event);
}

bootstrap().catch((error) => {
  const root = document.getElementById("game");
  if (root) {
    root.textContent = `Не удалось запустить игру: ${error instanceof Error ? error.message : "неизвестная ошибка"}`;
  }
});
