import Phaser from "phaser";

export type ProductionAssetManifest = {
  version: number;
  status: "awaiting_assets" | "ready";
  canvas: { width: number; height: number };
  village: {
    layers: {
      sky: string;
      far_world: string;
      mid_world: string;
      foreground?: string;
    };
  };
  tavern: {
    layers: {
      background: string;
      foreground?: string;
    };
  };
  characters: {
    player: string;
    oren: string;
  };
  props: {
    firewood: string;
  };
  ui?: {
    dialogue_frame?: string;
  };
};

const FALLBACK_MANIFEST: ProductionAssetManifest = {
  version: 1,
  status: "awaiting_assets",
  canvas: { width: 960, height: 540 },
  village: { layers: { sky: "", far_world: "", mid_world: "" } },
  tavern: { layers: { background: "" } },
  characters: { player: "", oren: "" },
  props: { firewood: "" }
};

const KEYS = {
  villageSky: "prod:village:sky",
  villageFar: "prod:village:far-world",
  villageMid: "prod:village:mid-world",
  villageForeground: "prod:village:foreground",
  tavernBackground: "prod:tavern:background",
  tavernForeground: "prod:tavern:foreground",
  player: "prod:character:player",
  oren: "prod:character:oren",
  firewood: "prod:prop:firewood"
} as const;

let currentManifest: ProductionAssetManifest = FALLBACK_MANIFEST;

export async function loadProductionManifest(): Promise<ProductionAssetManifest> {
  try {
    const response = await fetch("/assets/production/manifest.json", { cache: "no-store" });
    if (!response.ok) return FALLBACK_MANIFEST;
    const candidate: unknown = await response.json();
    return isProductionAssetManifest(candidate) ? candidate : FALLBACK_MANIFEST;
  } catch {
    return FALLBACK_MANIFEST;
  }
}

export function setProductionManifest(manifest: ProductionAssetManifest): void {
  currentManifest = manifest;
  document.body.dataset.artMode = manifest.status === "ready" ? "production-pending" : "greybox";
}

export function preloadVillageProductionArt(scene: Phaser.Scene): void {
  if (!productionEnabled()) return;
  queueImage(scene, KEYS.villageSky, currentManifest.village.layers.sky);
  queueImage(scene, KEYS.villageFar, currentManifest.village.layers.far_world);
  queueImage(scene, KEYS.villageMid, currentManifest.village.layers.mid_world);
  queueImage(scene, KEYS.villageForeground, currentManifest.village.layers.foreground);
  queueImage(scene, KEYS.player, currentManifest.characters.player);
  queueImage(scene, KEYS.firewood, currentManifest.props.firewood);
}

export function preloadTavernProductionArt(scene: Phaser.Scene): void {
  if (!productionEnabled()) return;
  queueImage(scene, KEYS.tavernBackground, currentManifest.tavern.layers.background);
  queueImage(scene, KEYS.tavernForeground, currentManifest.tavern.layers.foreground);
  queueImage(scene, KEYS.player, currentManifest.characters.player);
  queueImage(scene, KEYS.oren, currentManifest.characters.oren);
}

export function renderVillageProductionBackground(scene: Phaser.Scene): boolean {
  const required = [KEYS.villageSky, KEYS.villageFar, KEYS.villageMid];
  if (!productionEnabled() || !required.every((key) => scene.textures.exists(key))) {
    document.body.dataset.artMode = "greybox";
    return false;
  }

  addFullCanvasLayer(scene, KEYS.villageSky, -40);
  addFullCanvasLayer(scene, KEYS.villageFar, -30);
  addFullCanvasLayer(scene, KEYS.villageMid, -20);
  document.body.dataset.artMode = "production";
  return true;
}

export function renderVillageProductionForeground(scene: Phaser.Scene): void {
  if (scene.textures.exists(KEYS.villageForeground)) {
    addFullCanvasLayer(scene, KEYS.villageForeground, 40);
  }
}

export function renderTavernProductionBackground(scene: Phaser.Scene): boolean {
  if (!productionEnabled() || !scene.textures.exists(KEYS.tavernBackground)) {
    document.body.dataset.artMode = "greybox";
    return false;
  }

  addFullCanvasLayer(scene, KEYS.tavernBackground, -20);
  document.body.dataset.artMode = "production";
  return true;
}

export function renderTavernProductionForeground(scene: Phaser.Scene): void {
  if (scene.textures.exists(KEYS.tavernForeground)) {
    addFullCanvasLayer(scene, KEYS.tavernForeground, 40);
  }
}

export function createProductionPlayer(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (!scene.textures.exists(KEYS.player)) return null;
  return scene.add.image(x, y, KEYS.player)
    .setOrigin(0.5, 0.93)
    .setDisplaySize(48, 72)
    .setDepth(20);
}

export function createProductionOren(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (!scene.textures.exists(KEYS.oren)) return null;
  return scene.add.image(x, y, KEYS.oren)
    .setOrigin(0.5, 0.93)
    .setDisplaySize(64, 88)
    .setDepth(18);
}

export function createProductionFirewood(scene: Phaser.Scene, x: number, y: number): Phaser.GameObjects.Image | null {
  if (!scene.textures.exists(KEYS.firewood)) return null;
  return scene.add.image(x, y, KEYS.firewood)
    .setOrigin(0.5, 0.5)
    .setDisplaySize(44, 29)
    .setDepth(12);
}

function productionEnabled(): boolean {
  return currentManifest.status === "ready";
}

function queueImage(scene: Phaser.Scene, key: string, path?: string): void {
  if (!path || scene.textures.exists(key)) return;
  scene.load.image(key, assetUrl(path));
}

function assetUrl(path: string): string {
  return path.startsWith("/") ? path : `/assets/production/${path}`;
}

function addFullCanvasLayer(scene: Phaser.Scene, key: string, depth: number): Phaser.GameObjects.Image {
  return scene.add.image(480, 270, key)
    .setDisplaySize(960, 540)
    .setDepth(depth);
}

function isProductionAssetManifest(value: unknown): value is ProductionAssetManifest {
  if (!value || typeof value !== "object") return false;
  const manifest = value as Record<string, any>;
  return manifest.version === 1
    && (manifest.status === "awaiting_assets" || manifest.status === "ready")
    && manifest.canvas?.width === 960
    && manifest.canvas?.height === 540
    && hasString(manifest.village?.layers?.sky)
    && hasString(manifest.village?.layers?.far_world)
    && hasString(manifest.village?.layers?.mid_world)
    && hasString(manifest.tavern?.layers?.background)
    && hasString(manifest.characters?.player)
    && hasString(manifest.characters?.oren)
    && hasString(manifest.props?.firewood);
}

function hasString(value: unknown): value is string {
  return typeof value === "string";
}
