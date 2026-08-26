export type ProductionArtStatus = "awaiting_assets" | "partial" | "ready";

export type VillageLayerName =
  | "sky"
  | "distant_nature"
  | "mid_nature"
  | "architecture"
  | "gameplay"
  | "foreground";

export type NormalizedProductionManifest = {
  version: 2;
  sourceVersion: 1 | 2;
  status: ProductionArtStatus;
  canvas: { width: 960; height: 540 };
  village: {
    layers: Record<VillageLayerName, string>;
    parallax: { enabled: boolean };
  };
  tavern: { layers: { background: string; foreground: string } };
  characters: { player: string; oren: string };
  props: { firewood: string };
  ui: { dialogue_frame: string };
};

export const VILLAGE_PARALLAX_COEFFICIENTS: Readonly<Record<VillageLayerName, number>> = Object.freeze({
  sky: 0.005,
  distant_nature: 0.045,
  mid_nature: 0.16,
  architecture: 0.43,
  gameplay: 1,
  foreground: 1.4
});

const EMPTY_LAYERS: Record<VillageLayerName, string> = {
  sky: "",
  distant_nature: "",
  mid_nature: "",
  architecture: "",
  gameplay: "",
  foreground: ""
};

export const EMPTY_PRODUCTION_MANIFEST: NormalizedProductionManifest = {
  version: 2,
  sourceVersion: 2,
  status: "awaiting_assets",
  canvas: { width: 960, height: 540 },
  village: { layers: { ...EMPTY_LAYERS }, parallax: { enabled: false } },
  tavern: { layers: { background: "", foreground: "" } },
  characters: { player: "", oren: "" },
  props: { firewood: "" },
  ui: { dialogue_frame: "" }
};

type SceneReadiness = {
  ready: boolean;
  partial: boolean;
  present: number;
  available: string[];
  missing: string[];
};

export type ProductionReadiness = {
  village: SceneReadiness;
  tavern: SceneReadiness;
  player: boolean;
  oren: boolean;
  firewood: boolean;
};

export function normalizeProductionManifest(value: unknown): NormalizedProductionManifest {
  if (!isRecord(value)) return freshFallback();
  if (!hasCanvas(value.canvas)) return freshFallback();
  if (value.version === 1) return normalizeLegacyV1(value);
  if (value.version === 2) return normalizeV2(value);
  return freshFallback();
}

export function getProductionReadiness(manifest: NormalizedProductionManifest): ProductionReadiness {
  const requiredVillage: VillageLayerName[] = manifest.sourceVersion === 1
    ? ["sky", "distant_nature", "mid_nature"]
    : ["sky", "distant_nature", "mid_nature", "architecture", "gameplay"];

  const villageAvailable = (Object.keys(manifest.village.layers) as VillageLayerName[])
    .filter((name) => hasPath(manifest.village.layers[name]));
  const villageMissing = requiredVillage
    .filter((name) => !hasPath(manifest.village.layers[name]))
    .map((name) => `village.layers.${name}`);
  const villagePresent = villageAvailable.length;

  const tavernBackground = manifest.tavern.layers.background;
  const tavernAvailable = [
    hasPath(manifest.tavern.layers.background) ? "background" : "",
    hasPath(manifest.tavern.layers.foreground) ? "foreground" : ""
  ].filter(Boolean);
  const tavernMissing = hasPath(tavernBackground) ? [] : ["tavern.layers.background"];
  const tavernPresent = tavernAvailable.length;

  return {
    village: {
      ready: villageMissing.length === 0,
      partial: villagePresent > 0 && villageMissing.length > 0,
      present: villagePresent,
      available: villageAvailable,
      missing: villageMissing
    },
    tavern: {
      ready: tavernMissing.length === 0,
      partial: tavernPresent > 0 && tavernMissing.length > 0,
      present: tavernPresent,
      available: tavernAvailable,
      missing: tavernMissing
    },
    player: hasPath(manifest.characters.player),
    oren: hasPath(manifest.characters.oren),
    firewood: hasPath(manifest.props.firewood)
  };
}

export function parallaxOffset(layer: VillageLayerName, cameraTravel: number): number {
  if (!Number.isFinite(cameraTravel) || cameraTravel === 0) return 0;
  return -cameraTravel * VILLAGE_PARALLAX_COEFFICIENTS[layer];
}

function normalizeV2(value: Record<string, unknown>): NormalizedProductionManifest {
  const status = artStatus(value.status);
  if (!status) return freshFallback();

  const village = asRecord(value.village);
  const villageLayers = asRecord(village.layers);
  const parallax = asRecord(village.parallax);
  const tavern = asRecord(value.tavern);
  const tavernLayers = asRecord(tavern.layers);
  const characters = asRecord(value.characters);
  const props = asRecord(value.props);
  const ui = asRecord(value.ui);

  return {
    version: 2,
    sourceVersion: 2,
    status,
    canvas: { width: 960, height: 540 },
    village: {
      layers: {
        sky: path(villageLayers.sky),
        distant_nature: path(villageLayers.distant_nature),
        mid_nature: path(villageLayers.mid_nature),
        architecture: path(villageLayers.architecture),
        gameplay: path(villageLayers.gameplay),
        foreground: path(villageLayers.foreground)
      },
      parallax: { enabled: parallax.enabled === true }
    },
    tavern: {
      layers: {
        background: path(tavernLayers.background),
        foreground: path(tavernLayers.foreground)
      }
    },
    characters: {
      player: path(characters.player),
      oren: path(characters.oren)
    },
    props: { firewood: path(props.firewood) },
    ui: { dialogue_frame: path(ui.dialogue_frame) }
  };
}

function normalizeLegacyV1(value: Record<string, unknown>): NormalizedProductionManifest {
  const status = value.status === "ready" ? "ready" : "awaiting_assets";
  if (status !== "ready") return freshFallback(1);

  const village = asRecord(value.village);
  const villageLayers = asRecord(village.layers);
  const tavern = asRecord(value.tavern);
  const tavernLayers = asRecord(tavern.layers);
  const characters = asRecord(value.characters);
  const props = asRecord(value.props);
  const ui = asRecord(value.ui);

  return {
    version: 2,
    sourceVersion: 1,
    status,
    canvas: { width: 960, height: 540 },
    village: {
      layers: {
        ...EMPTY_LAYERS,
        sky: path(villageLayers.sky),
        distant_nature: path(villageLayers.far_world),
        mid_nature: path(villageLayers.mid_world),
        foreground: path(villageLayers.foreground)
      },
      parallax: { enabled: false }
    },
    tavern: {
      layers: {
        background: path(tavernLayers.background),
        foreground: path(tavernLayers.foreground)
      }
    },
    characters: {
      player: path(characters.player),
      oren: path(characters.oren)
    },
    props: { firewood: path(props.firewood) },
    ui: { dialogue_frame: path(ui.dialogue_frame) }
  };
}

function freshFallback(sourceVersion: 1 | 2 = 2): NormalizedProductionManifest {
  return {
    ...EMPTY_PRODUCTION_MANIFEST,
    sourceVersion,
    village: {
      layers: { ...EMPTY_PRODUCTION_MANIFEST.village.layers },
      parallax: { ...EMPTY_PRODUCTION_MANIFEST.village.parallax }
    },
    tavern: { layers: { ...EMPTY_PRODUCTION_MANIFEST.tavern.layers } },
    characters: { ...EMPTY_PRODUCTION_MANIFEST.characters },
    props: { ...EMPTY_PRODUCTION_MANIFEST.props },
    ui: { ...EMPTY_PRODUCTION_MANIFEST.ui }
  };
}

function hasCanvas(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return value.width === 960 && value.height === 540;
}

function artStatus(value: unknown): ProductionArtStatus | null {
  return value === "awaiting_assets" || value === "partial" || value === "ready" ? value : null;
}

function path(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function hasPath(value: string): boolean {
  return value.length > 0;
}

function asRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
