import Phaser from "phaser";

import {
  createPrototypeFirewood,
  createPrototypeOren,
  createPrototypePlayer,
  preloadTavernPrototypeArt,
  preloadVillagePrototypeArt,
  renderTavernPrototypeBackground,
  renderVillagePrototypeBackground
} from "./prototypeArt";
import {
  EMPTY_PRODUCTION_MANIFEST,
  VILLAGE_PARALLAX_COEFFICIENTS,
  getProductionReadiness,
  normalizeProductionManifest,
  type NormalizedProductionManifest,
  type ProductionReadiness,
  type VillageLayerName
} from "./productionManifest";

const VILLAGE_KEYS: Record<VillageLayerName, string> = {
  sky: "prod:village:sky",
  distant_nature: "prod:village:distant-nature",
  mid_nature: "prod:village:mid-nature",
  architecture: "prod:village:architecture",
  gameplay: "prod:village:gameplay",
  foreground: "prod:village:foreground"
};

const VILLAGE_DEPTHS: Record<VillageLayerName, number> = {
  sky: -60,
  distant_nature: -50,
  mid_nature: -40,
  architecture: 2,
  gameplay: 4,
  foreground: 40
};

const KEYS = {
  tavernBackground: "prod:tavern:background",
  tavernForeground: "prod:tavern:foreground",
  player: "prod:character:player",
  oren: "prod:character:oren",
  firewood: "prod:prop:firewood"
} as const;

const V2_VILLAGE_CORE: VillageLayerName[] = ["sky", "distant_nature", "mid_nature", "architecture", "gameplay"];
const V1_VILLAGE_CORE: VillageLayerName[] = ["sky", "distant_nature", "mid_nature"];

let currentManifest: NormalizedProductionManifest = EMPTY_PRODUCTION_MANIFEST;
let currentReadiness: ProductionReadiness = getProductionReadiness(currentManifest);

export async function loadProductionManifest(): Promise<NormalizedProductionManifest> {
  try {
    const response = await fetch("/assets/production/manifest.json", { cache: "no-store" });
    if (!response.ok) return normalizeProductionManifest(null);
    return normalizeProductionManifest(await response.json());
  } catch {
    return normalizeProductionManifest(null);
  }
}

export function setProductionManifest(manifest: NormalizedProductionManifest): void {
  currentManifest = manifest;
  currentReadiness = getProductionReadiness(manifest);
  publishManifestDiagnostics();
}

export function preloadVillageProductionArt(scene: Phaser.Scene): void {
  preloadVillagePrototypeArt(scene);
  for (const layer of villageLayerNames()) {
    queueImage(scene, VILLAGE_KEYS[layer], currentManifest.village.layers[layer]);
  }
  if (currentReadiness.player) queueImage(scene, KEYS.player, currentManifest.characters.player);
  if (currentReadiness.firewood) queueImage(scene, KEYS.firewood, currentManifest.props.firewood);
}

export function preloadTavernProductionArt(scene: Phaser.Scene): void {
  preloadTavernPrototypeArt(scene);
  if (currentReadiness.tavern.ready) {
    queueImage(scene, KEYS.tavernBackground, currentManifest.tavern.layers.background);
    queueImage(scene, KEYS.tavernForeground, currentManifest.tavern.layers.foreground);
  }
  if (currentReadiness.player) queueImage(scene, KEYS.player, currentManifest.characters.player);
  if (currentReadiness.oren) queueImage(scene, KEYS.oren, currentManifest.characters.oren);
}

export function renderVillageProductionBackground(scene: Phaser.Scene): boolean {
  if (renderVillagePrototypeBackground(scene)) return true;

  const declared = villageLayerNames().filter((layer) => Boolean(currentManifest.village.layers[layer]));
  const loaded = declared.filter((layer) => scene.textures.exists(VILLAGE_KEYS[layer]));
  const runtimeMissing = declared
    .filter((layer) => !scene.textures.exists(VILLAGE_KEYS[layer]))
    .map((layer) => `texture:${layer}`);
  const required = requiredVillageLayers();
  const fullReady = currentReadiness.village.ready
    && required.every((layer) => scene.textures.exists(VILLAGE_KEYS[layer]));

  if (loaded.length === 0) {
    markSceneFallback("village", runtimeMissing);
    return false;
  }

  for (const layer of loaded) {
    if (layer === "foreground") continue;
    addVillageCanvasLayer(scene, layer);
  }

  if (runtimeMissing.length > 0) appendRuntimeMissing(runtimeMissing);
  document.body.dataset.artMode = fullReady ? "production" : "partial-production";
  document.body.dataset.villageArt = fullReady ? "production" : "partial-production";
  return fullReady;
}

export function renderVillageProductionForeground(scene: Phaser.Scene): void {
  if (document.body.dataset.villageArt === "prototype") return;
  const layer: VillageLayerName = "foreground";
  if (!currentManifest.village.layers[layer]) return;
  if (scene.textures.exists(VILLAGE_KEYS[layer])) {
    addVillageCanvasLayer(scene, layer);
  } else {
    appendRuntimeMissing(["texture:foreground"]);
  }
}

export function renderTavernProductionBackground(scene: Phaser.Scene): boolean {
  if (renderTavernPrototypeBackground(scene)) return true;

  if (!currentReadiness.tavern.ready || !scene.textures.exists(KEYS.tavernBackground)) {
    markSceneFallback("tavern", currentReadiness.tavern.ready ? ["texture:tavern.background"] : []);
    return false;
  }

  addFullCanvasLayer(scene, KEYS.tavernBackground, -20);
  document.body.dataset.artMode = "production";
  document.body.dataset.tavernArt = "production";
  return true;
}

export function renderTavernProductionForeground(scene: Phaser.Scene): void {
  if (document.body.dataset.tavernArt === "prototype") return;
  if (!currentReadiness.tavern.ready || !currentManifest.tavern.layers.foreground) return;
  if (scene.textures.exists(KEYS.tavernForeground)) addFullCanvasLayer(scene, KEYS.tavernForeground, 40);
}

export function createProductionPlayer(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (document.body.dataset.artMode === "prototype") {
    const prototype = createPrototypePlayer(scene, x, y);
    if (prototype) return prototype;
  }
  if (!currentReadiness.player || !scene.textures.exists(KEYS.player)) {
    if (currentReadiness.player) document.body.dataset.playerArt = "fallback-load-error";
    return null;
  }
  document.body.dataset.playerArt = "production";
  return scene.add.image(x, y, KEYS.player)
    .setOrigin(0.5, 0.93)
    .setDisplaySize(48, 72)
    .setDepth(20);
}

export function createProductionOren(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (document.body.dataset.artMode === "prototype") {
    const prototype = createPrototypeOren(scene, x, y);
    if (prototype) return prototype;
  }
  if (!currentReadiness.oren || !scene.textures.exists(KEYS.oren)) {
    if (currentReadiness.oren) document.body.dataset.orenArt = "fallback-load-error";
    return null;
  }
  document.body.dataset.orenArt = "production";
  return scene.add.image(x, y, KEYS.oren)
    .setOrigin(0.5, 0.93)
    .setDisplaySize(64, 88)
    .setDepth(18);
}

export function createProductionFirewood(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (document.body.dataset.artMode === "prototype") {
    const prototype = createPrototypeFirewood(scene, x, y);
    if (prototype) return prototype;
  }
  if (!currentReadiness.firewood || !scene.textures.exists(KEYS.firewood)) {
    if (currentReadiness.firewood) document.body.dataset.firewoodArt = "fallback-load-error";
    return null;
  }
  document.body.dataset.firewoodArt = "production";
  return scene.add.image(x, y, KEYS.firewood)
    .setOrigin(0.5, 0.5)
    .setDisplaySize(44, 29)
    .setDepth(12);
}

function publishManifestDiagnostics(): void {
  const villageState = currentReadiness.village.ready
    ? "production-pending"
    : currentReadiness.village.partial ? "partial-production-pending" : "greybox";
  const tavernState = currentReadiness.tavern.ready
    ? "production-pending"
    : currentReadiness.tavern.partial ? "partial-fallback" : "greybox";

  document.body.dataset.artMode = "greybox";
  document.body.dataset.artManifest = `source-v${currentManifest.sourceVersion}:v2:${currentManifest.status}`;
  document.body.dataset.villageArt = villageState;
  document.body.dataset.tavernArt = tavernState;
  document.body.dataset.playerArt = currentReadiness.player ? "production-pending" : "fallback";
  document.body.dataset.orenArt = currentReadiness.oren ? "production-pending" : "fallback";
  document.body.dataset.firewoodArt = currentReadiness.firewood ? "production-pending" : "fallback";

  const missing = [
    ...currentReadiness.village.missing,
    ...currentReadiness.tavern.missing,
    ...(!currentReadiness.player ? ["characters.player"] : []),
    ...(!currentReadiness.oren ? ["characters.oren"] : []),
    ...(!currentReadiness.firewood ? ["props.firewood"] : [])
  ];
  document.body.dataset.artMissing = missing.join(",");
}

function markSceneFallback(sceneName: "village" | "tavern", runtimeMissing: string[]): void {
  document.body.dataset.artMode = "greybox";
  document.body.dataset[sceneName === "village" ? "villageArt" : "tavernArt"] = runtimeMissing.length > 0
    ? "fallback-load-error"
    : "greybox";
  if (runtimeMissing.length > 0) appendRuntimeMissing(runtimeMissing);
}

function appendRuntimeMissing(runtimeMissing: string[]): void {
  const existing = document.body.dataset.artMissing;
  document.body.dataset.artMissing = [existing, ...runtimeMissing].filter(Boolean).join(",");
}

function requiredVillageLayers(): VillageLayerName[] {
  return currentManifest.sourceVersion === 1 ? V1_VILLAGE_CORE : V2_VILLAGE_CORE;
}

function villageLayerNames(): VillageLayerName[] {
  return ["sky", "distant_nature", "mid_nature", "architecture", "gameplay", "foreground"];
}

function queueImage(scene: Phaser.Scene, key: string, path?: string): void {
  if (!path || scene.textures.exists(key)) return;
  scene.load.image(key, assetUrl(path));
}

function assetUrl(path: string): string {
  return path.startsWith("/") ? path : `/assets/production/${path}`;
}

function addVillageCanvasLayer(scene: Phaser.Scene, layer: VillageLayerName): Phaser.GameObjects.Image {
  const image = addFullCanvasLayer(scene, VILLAGE_KEYS[layer], VILLAGE_DEPTHS[layer]);
  if (currentManifest.village.parallax.enabled) {
    image.setScrollFactor(VILLAGE_PARALLAX_COEFFICIENTS[layer], 1);
  }
  return image;
}

function addFullCanvasLayer(scene: Phaser.Scene, key: string, depth: number): Phaser.GameObjects.Image {
  return scene.add.image(480, 270, key)
    .setDisplaySize(960, 540)
    .setDepth(depth);
}
