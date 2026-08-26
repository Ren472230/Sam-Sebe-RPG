import type { GameApi } from "./api";
import type { ClientState } from "./state";
import type { DialoguePanel } from "./ui/DialoguePanel";

export type Runtime = {
  api: GameApi;
  state: ClientState;
  dialogue: DialoguePanel;
};

let current: Runtime | null = null;

export function setRuntime(runtime: Runtime): void {
  current = runtime;
}

export function getRuntime(): Runtime {
  if (!current) throw new Error("Runtime not initialized");
  return current;
}
