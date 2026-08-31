export const PROTOTYPE_ASSETS = {
  villageBackground: "prototype/village.svg",
  tavernBackground: "prototype/tavern.svg",
  player: "prototype/player.svg",
  oren: "prototype/oren.svg",
  firewood: "prototype/firewood.svg"
} as const;

export type PrototypeAssetName = keyof typeof PROTOTYPE_ASSETS;

export type PrototypeReadiness = {
  village: boolean;
  tavern: boolean;
};

const VILLAGE_REQUIRED: PrototypeAssetName[] = ["villageBackground", "player", "firewood"];
const TAVERN_REQUIRED: PrototypeAssetName[] = ["tavernBackground", "player", "oren"];

export function getPrototypeReadiness(available: ReadonlySet<PrototypeAssetName>): PrototypeReadiness {
  return {
    village: VILLAGE_REQUIRED.every((name) => available.has(name)),
    tavern: TAVERN_REQUIRED.every((name) => available.has(name))
  };
}

export function prototypeAssetUrl(path: string): string {
  return path.startsWith("/") ? path : `/assets/${path}`;
}
