export const PLAYER_SPEED_PX_PER_MS = 0.22;
export const MAX_MOVEMENT_SUBSTEP_MS = 50;
export const MAX_MOVEMENT_CATCHUP_MS = 200;

export type HeldMovementKey = {
  isDown: boolean;
  getDuration: () => number;
  timeDown?: number;
};

type HeldMovementState = {
  backlogMs: number;
  lastDurationMs: number;
  lastTimeDown?: number;
};

const heldMovementState = new WeakMap<object, HeldMovementState>();

export function effectiveHeldDelta(deltaMs: number, key: HeldMovementKey | null): number {
  if (!key?.isDown || !Number.isFinite(deltaMs) || deltaMs <= 0) return 0;
  const heldMs = key.getDuration();
  if (!Number.isFinite(heldMs) || heldMs <= 0) return 0;

  const timeDown = Number.isFinite(key.timeDown) ? key.timeDown : undefined;
  const previousState = heldMovementState.get(key as object);
  const isNewPress = !previousState
    || (timeDown !== undefined && previousState.lastTimeDown !== undefined && timeDown !== previousState.lastTimeDown)
    || heldMs < (previousState?.lastDurationMs ?? 0);
  const state: HeldMovementState = isNewPress
    ? { backlogMs: 0, lastDurationMs: 0, lastTimeDown: timeDown }
    : previousState;

  const heldAdvanceMs = isNewPress
    ? Math.min(deltaMs, heldMs)
    : Math.max(0, heldMs - state.lastDurationMs);
  const observedElapsedMs = isNewPress
    ? heldAdvanceMs
    : Math.max(Math.min(deltaMs, heldMs), heldAdvanceMs);

  state.backlogMs += observedElapsedMs;
  state.lastDurationMs = heldMs;
  state.lastTimeDown = timeDown;

  const appliedMs = Math.min(state.backlogMs, MAX_MOVEMENT_CATCHUP_MS);
  state.backlogMs -= appliedMs;
  heldMovementState.set(key as object, state);
  return appliedMs;
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

export function applyAxisMovementDeltas(
  xDeltaMs: number,
  yDeltaMs: number,
  applyStep: (xDistancePx: number, yDistancePx: number) => void,
  speedPxPerMs = PLAYER_SPEED_PX_PER_MS,
  maxSubstepMs = MAX_MOVEMENT_SUBSTEP_MS
): void {
  if (!Number.isFinite(speedPxPerMs) || speedPxPerMs < 0) return;
  if (!Number.isFinite(maxSubstepMs) || maxSubstepMs <= 0) return;

  let remainingX = Number.isFinite(xDeltaMs) && xDeltaMs > 0 ? xDeltaMs : 0;
  let remainingY = Number.isFinite(yDeltaMs) && yDeltaMs > 0 ? yDeltaMs : 0;
  while (remainingX > 0 || remainingY > 0) {
    const stepX = Math.min(remainingX, maxSubstepMs);
    const stepY = Math.min(remainingY, maxSubstepMs);
    applyStep(speedPxPerMs * stepX, speedPxPerMs * stepY);
    remainingX -= stepX;
    remainingY -= stepY;
  }
}
