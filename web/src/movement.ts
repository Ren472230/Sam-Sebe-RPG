export const PLAYER_SPEED_PX_PER_MS = 0.22;
export const MAX_MOVEMENT_SUBSTEP_MS = 50;

export type HeldMovementKey = {
  isDown: boolean;
  getDuration: () => number;
};

export function effectiveHeldDelta(deltaMs: number, key: HeldMovementKey | null): number {
  if (!key?.isDown || !Number.isFinite(deltaMs) || deltaMs <= 0) return 0;
  const heldMs = key.getDuration();
  if (!Number.isFinite(heldMs) || heldMs <= 0) return 0;
  return Math.min(deltaMs, heldMs);
}

export function applyMovementDelta(
  deltaMs: number,
  applyStep: (distancePx: number) => void,
  speedPxPerMs = PLAYER_SPEED_PX_PER_MS,
  maxSubstepMs = MAX_MOVEMENT_SUBSTEP_MS
): void {
  if (!Number.isFinite(deltaMs) || deltaMs <= 0) return;
  if (!Number.isFinite(speedPxPerMs) || speedPxPerMs < 0) return;
  if (!Number.isFinite(maxSubstepMs) || maxSubstepMs <= 0) return;

  let remainingMs = deltaMs;
  while (remainingMs > 0) {
    const stepMs = Math.min(remainingMs, maxSubstepMs);
    applyStep(speedPxPerMs * stepMs);
    remainingMs -= stepMs;
  }
}
