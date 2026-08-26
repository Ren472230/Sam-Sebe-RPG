import Phaser from "phaser";

import { GameApi } from "./api";
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

bootstrap().catch((error) => {
  const root = document.getElementById("game");
  if (root) {
    root.textContent = `Не удалось запустить игру: ${error instanceof Error ? error.message : "неизвестная ошибка"}`;
  }
});
