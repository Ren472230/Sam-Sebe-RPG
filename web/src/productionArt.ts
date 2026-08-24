import Phaser from "phaser";

export type ProductionAssetManifest = {
  version: string;
  enabled: boolean;
  assets: {
    village: {
      sky: string;
      farWorld: string;
      midWorld: string;
      foreground?: string;
    };
    tavern: {
      background: string;
      foreground?: string;
    };
    characters: {
      player: string;
      oren: string;
    };
    props: {
      firewood: string;
    };
    ui?: {
      dialogueFrame?: string;
    };
  };
};

const FALLBACK_MANIFEST: ProductionAssetManifest = {
  version: "greybox",
  enabled: false,
  assets: {
    village: { sky: "", farWorld: "", midWorld: "" },
    tavern: { background: "" },
    characters: { player: "", oren: "" },
    props: { firewood: "" }
  }
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
  document.body.dataset.artMode = manifest.enabled ? "production-pending" : "greybox";
}

export function getProductionManifest(): ProductionAssetManifest {
  return currentManifest;
}

export function preloadVillageProductionArt(scene: Phaser.Scene): void {
  if (!currentManifest.enabled) return;
  queueImage(scene, KEYS.villageSky, currentManifest.assets.village.sky);
  queueImage(scene, KEYS.villageFar, currentManifest.assets.village.farWorld);
  queueImage(scene, KEYS.villageMid, currentManifest.assets.village.midWorld);
  queueImage(scene, KEYS.villageForeground, currentManifest.assets.village.foreground);
  queueImage(scene, KEYS.player, currentManifest.assets.characters.player);
  queueImage(scene, KEYS.firewood, currentManifest.assets.props.firewood);
}

export function preloadTavernProductionArt(scene: Phaser.Scene): void {
  if (!currentManifest.enabled) return;
  queueImage(scene, KEYS.tavernBackground, currentManifest.assets.tavern.background);
  queueImage(scene, KEYS.tavernForeground, currentManifest.assets.tavern.foreground);
  queueImage(scene, KEYS.player, currentManifest.assets.characters.player);
  queueImage(scene, KEYS.oren, currentManifest.assets.characters.oren);
}

export function renderVillageProductionBackground(scene: Phaser.Scene): boolean {
  const required = [KEYS.villageSky, KEYS.villageFar, KEYS.villageMid];
  if (!currentManifest.enabled || !required.every((key) => scene.textures.exists(key))) {
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
  if (!currentManifest.enabled || !scene.textures.exists(KEYS.tavernBackground)) {
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

function queueImage(scene: Phaser.Scene, key: string, path?: string): void {
  if (!path || scene.textures.exists(key)) return;
  scene.load.image(key, path);
}

function addFullCanvasLayer(scene: Phaser.Scene, key: string, depth: number): Phaser.GameObjects.Image {
  return scene.add.image(480, 270, key)
    .setDisplaySize(960, 540)
    .setDepth(depth);
}

function isProductionAssetManifest(value: unknown): value is ProductionAssetManifest {
  if (!value || typeof value !== "object") return false;
  const manifest = value as Partial<ProductionAssetManifest>;
  if (typeof manifest.version !== "string" || typeof manifest.enabled !== "boolean") return false;
  const assets = manifest.assets;
  if (!assets || typeof assets !== "object") return false;
  return hasString(assets.village?.sky)
    && hasString(assets.village?.farWorld)
    && hasString(assets.village?.midWorld)
    && hasString(assets.tavern?.background)
    && hasString(assets.characters?.player)
    && hasString(assets.characters?.oren)
    && hasString(assets.props?.firewood);
}

function hasString(value: unknown): value is string {
  return typeof value === "string";
}
