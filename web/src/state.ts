import type { GameApi, GameSnapshot } from "./api";

export class ClientState {
  snapshot: GameSnapshot | null = null;
  private listeners = new Set<(snapshot: GameSnapshot) => void>();

  constructor(public readonly api: GameApi, public readonly playerId: string) {}

  async refresh(): Promise<GameSnapshot> {
    this.snapshot = await this.api.getState(this.playerId);
    for (const listener of this.listeners) listener(this.snapshot);
    return this.snapshot;
  }

  subscribe(listener: (snapshot: GameSnapshot) => void): () => void {
    this.listeners.add(listener);
    if (this.snapshot) listener(this.snapshot);
    return () => this.listeners.delete(listener);
  }
}
