export const PLAYER_SPEED_PX_PER_MS = 0.22;
export const MAX_MOVEMENT_SUBSTEP_MS = 50;
export const MAX_MOVEMENT_CATCHUP_MS = 400;

export type HeldMovementKey = {
  isDown: boolean;
  getDuration: () => number;
  timeDown?: number;
  timeUp?: number;
  duration?: number;
};

type HeldMovementState = {
  consumedMs: number;
  lastTimeDown?: number;
  releaseConsumed: boolean;
  observedWhileDown: boolean;
};

const heldMovementState = new WeakMap<object, HeldMovementState>();

function releasedHeldDurationMs(key: HeldMovementKey): number {
  const timeDown = Number.isFinite(key.timeDown) ? Number(key.timeDown) : undefined;
  if (timeDown === undefined || timeDown <= 0) return 0;
  const timeUp = Number.isFinite(key.timeUp) ? Number(key.timeUp) : undefined;
  if (timeUp === undefined || timeUp < timeDown) return 0;
  return timeUp - timeDown;
}

export function effectiveHeldDelta(
  deltaMs: number,
  key: HeldMovementKey | null,
  _nowMs = Number.NaN
): number {
  if (!key || !Number.isFinite(deltaMs) || deltaMs <= 0) return 0;

  const timeDown = Number.isFinite(key.timeDown) ? Number(key.timeDown) : undefined;
  const previousState = heldMovementState.get(key as object);
  const isNewPress = !previousState
    || (key.isDown && previousState.releaseConsumed)
    || (timeDown !== undefined && previousState.lastTimeDown !== timeDown);
  const state: HeldMovementState = isNewPress
    ? { consumedMs: 0, lastTimeDown: timeDown, releaseConsumed: false, observedWhileDown: false }
    : previousState;

  if (key.isDown) {
    const heldMs = key.getDuration();
    if (!Number.isFinite(heldMs) || heldMs <= 0) return 0;
    const unconsumedHeldMs = Math.max(0, heldMs - state.consumedMs);
    const appliedMs = Math.min(deltaMs, unconsumedHeldMs, MAX_MOVEMENT_CATCHUP_MS);
    state.consumedMs += appliedMs;
    state.lastTimeDown = timeDown;
    state.releaseConsumed = false;
    state.observedWhileDown = state.observedWhileDown || appliedMs > 0;
    heldMovementState.set(key as object, state);
    return appliedMs;
  }

  if (state.releaseConsumed) return 0;
  if (state.observedWhileDown) {
    state.lastTimeDown = timeDown;
    state.releaseConsumed = true;
    heldMovementState.set(key as object, state);
    return 0;
  }

  const heldMs = releasedHeldDurationMs(key);
  if (!Number.isFinite(heldMs) || heldMs <= 0) {
    if (timeDown !== undefined && timeDown > 0) {
      state.releaseConsumed = true;
      heldMovementState.set(key as object, state);
    }
    return 0;
  }

  const remainingMs = Math.max(0, heldMs - state.consumedMs);
  const appliedMs = Math.min(remainingMs, MAX_MOVEMENT_CATCHUP_MS);
  state.consumedMs += appliedMs;
  state.lastTimeDown = timeDown;
  state.releaseConsumed = true;
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
