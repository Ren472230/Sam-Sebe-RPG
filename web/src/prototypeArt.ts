import type Phaser from "phaser";

import { PROTOTYPE_ASSETS, prototypeAssetUrl } from "./prototypeManifest";

const KEYS = {
  villageBackground: "prototype:village:background",
  tavernBackground: "prototype:tavern:background",
  player: "prototype:character:player",
  oren: "prototype:character:oren",
  firewood: "prototype:prop:firewood"
} as const;

export function preloadVillagePrototypeArt(scene: Phaser.Scene): void {
  queueImage(scene, KEYS.villageBackground, PROTOTYPE_ASSETS.villageBackground);
  queueImage(scene, KEYS.player, PROTOTYPE_ASSETS.player);
  queueImage(scene, KEYS.firewood, PROTOTYPE_ASSETS.firewood);
}

export function preloadTavernPrototypeArt(scene: Phaser.Scene): void {
  queueImage(scene, KEYS.tavernBackground, PROTOTYPE_ASSETS.tavernBackground);
  queueImage(scene, KEYS.player, PROTOTYPE_ASSETS.player);
  queueImage(scene, KEYS.oren, PROTOTYPE_ASSETS.oren);
}

export function renderVillagePrototypeBackground(scene: Phaser.Scene): boolean {
  if (!hasVillageTextures(scene)) {
    document.body.dataset.villageArt = "prototype-unavailable";
    return false;
  }
  addFullCanvasLayer(scene, KEYS.villageBackground, -20);
  document.body.dataset.artMode = "prototype";
  document.body.dataset.villageArt = "prototype";
  return true;
}

export function renderTavernPrototypeBackground(scene: Phaser.Scene): boolean {
  if (!hasTavernTextures(scene)) {
    document.body.dataset.tavernArt = "prototype-unavailable";
    return false;
  }
  addFullCanvasLayer(scene, KEYS.tavernBackground, -20);
  document.body.dataset.artMode = "prototype";
  document.body.dataset.tavernArt = "prototype";
  return true;
}

export function createPrototypePlayer(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (!scene.textures.exists(KEYS.player)) return null;
  document.body.dataset.playerArt = "prototype";
  return scene.add.image(x, y, KEYS.player)
    .setOrigin(0.5, 0.93)
    .setDisplaySize(48, 72)
    .setDepth(20);
}

export function createPrototypeOren(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (!scene.textures.exists(KEYS.oren)) return null;
  document.body.dataset.orenArt = "prototype";
  return scene.add.image(x, y, KEYS.oren)
    .setOrigin(0.5, 0.93)
    .setDisplaySize(64, 88)
    .setDepth(18);
}

export function createPrototypeFirewood(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (!scene.textures.exists(KEYS.firewood)) return null;
  document.body.dataset.firewoodArt = "prototype";
  return scene.add.image(x, y, KEYS.firewood)
    .setOrigin(0.5, 0.5)
    .setDisplaySize(44, 29)
    .setDepth(12);
}

function hasVillageTextures(scene: Phaser.Scene): boolean {
  return [KEYS.villageBackground, KEYS.player, KEYS.firewood]
    .every((key) => scene.textures.exists(key));
}

function hasTavernTextures(scene: Phaser.Scene): boolean {
  return [KEYS.tavernBackground, KEYS.player, KEYS.oren]
    .every((key) => scene.textures.exists(key));
}

function queueImage(scene: Phaser.Scene, key: string, path: string): void {
  if (scene.textures.exists(key)) return;
  scene.load.svg(key, prototypeAssetUrl(path));
}

function addFullCanvasLayer(scene: Phaser.Scene, key: string, depth: number): Phaser.GameObjects.Image {
  return scene.add.image(480, 270, key)
    .setDisplaySize(960, 540)
    .setDepth(depth);
}
