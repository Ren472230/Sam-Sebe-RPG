const TOUCH_LAYOUT_QUERY = "(max-width: 700px)";

export function movementControlHint(): string {
  return isTouchControlLayout()
    ? "Экранные кнопки – движение · Действие – взаимодействие"
    : "WASD — движение · E — взаимодействие";
}

export function actionControlHint(action: string): string {
  return isTouchControlLayout() ? `Действие – ${action}` : `E — ${action}`;
}

function isTouchControlLayout(): boolean {
  return window.matchMedia(TOUCH_LAYOUT_QUERY).matches;
}
