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
};

const heldMovementState = new WeakMap<object, HeldMovementState>();

function monotonicNowMs(): number {
  return typeof performance === "undefined" ? Number.NaN : performance.now();
}

function observedHeldDurationMs(key: HeldMovementKey, nowMs: number): number {
  const timeDown = Number.isFinite(key.timeDown) ? Number(key.timeDown) : undefined;
  if (key.isDown) {
    if (timeDown !== undefined && timeDown > 0 && Number.isFinite(nowMs)) {
      const wallHeldMs = nowMs - timeDown;
      if (wallHeldMs >= 0) return wallHeldMs;
    }
    return key.getDuration();
  }

  // Phaser updates timeUp/duration even for an extra keyup event while the key is
  // already up. A release can therefore be trusted only when it belongs to a real
  // physical press with a positive timeDown. Replay protection lives in
  // effectiveHeldDelta so a later synthetic keyup cannot extend the same press.
  if (timeDown === undefined || timeDown <= 0) return 0;
  const timeUp = Number.isFinite(key.timeUp) ? Number(key.timeUp) : undefined;
  if (timeUp === undefined || timeUp < timeDown) return 0;
  return timeUp - timeDown;
}

export function effectiveHeldDelta(
  deltaMs: number,
  key: HeldMovementKey | null,
  nowMs = monotonicNowMs()
): number {
  if (!key || !Number.isFinite(deltaMs) || deltaMs <= 0) return 0;

  const timeDown = Number.isFinite(key.timeDown) ? Number(key.timeDown) : undefined;
  const previousState = heldMovementState.get(key as object);
  const isNewPress = !previousState
    || (timeDown !== undefined && previousState.lastTimeDown !== timeDown);
  const state: HeldMovementState = isNewPress
    ? { consumedMs: 0, lastTimeDown: timeDown, releaseConsumed: false }
    : previousState;

  if (!key.isDown && state.releaseConsumed) return 0;

  const heldMs = observedHeldDurationMs(key, nowMs);
  if (!Number.isFinite(heldMs) || heldMs <= 0) {
    if (!key.isDown && timeDown !== undefined && timeDown > 0) {
      state.releaseConsumed = true;
      heldMovementState.set(key as object, state);
    }
    return 0;
  }

  const remainingMs = Math.max(0, heldMs - state.consumedMs);
  const appliedMs = Math.min(remainingMs, MAX_MOVEMENT_CATCHUP_MS);
  state.consumedMs += appliedMs;
  state.lastTimeDown = timeDown;
  if (!key.isDown) state.releaseConsumed = true;
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
