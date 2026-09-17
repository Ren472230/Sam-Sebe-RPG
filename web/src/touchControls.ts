import "./touchFeedback.css";

type TouchControl = "W" | "A" | "S" | "D" | "E";

type KeySpec = {
  key: string;
  code: string;
  keyCode: number;
};

const KEYS: Record<TouchControl, KeySpec> = {
  W: { key: "w", code: "KeyW", keyCode: 87 },
  A: { key: "a", code: "KeyA", keyCode: 65 },
  S: { key: "s", code: "KeyS", keyCode: 83 },
  D: { key: "d", code: "KeyD", keyCode: 68 },
  E: { key: "e", code: "KeyE", keyCode: 69 }
};

const TOUCH_ACTION_PREFIX = "Действие – ";
const DEFAULT_ACTION_CONTEXT = "взаимодействие";
const activePointers = new Map<number, TouchControl>();

installTouchControls();

function installTouchControls(): void {
  const app = document.getElementById("app");
  if (!app || document.getElementById("touch-controls")) return;

  const root = document.createElement("nav");
  root.id = "touch-controls";
  root.setAttribute("aria-label", "Сенсорное управление");

  const dpad = document.createElement("div");
  dpad.className = "touch-dpad";
  dpad.append(
    controlButton("W", "Вверх", "↑", "touch-up"),
    controlButton("A", "Влево", "←", "touch-left"),
    controlButton("S", "Вниз", "↓", "touch-down"),
    controlButton("D", "Вправо", "→", "touch-right")
  );

  const action = actionButton();
  root.append(dpad, action);

  const playtestTools = document.getElementById("playtest-tools");
  const dialogue = document.getElementById("dialogue");
  if (playtestTools) app.insertBefore(root, playtestTools);
  else if (dialogue) app.insertBefore(root, dialogue);
  else app.append(root);

  bindActionContext(action);

  for (const button of root.querySelectorAll<HTMLButtonElement>("button[data-touch-key]")) {
    button.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const control = button.dataset.touchKey as TouchControl | undefined;
      if (!control || activePointers.has(event.pointerId)) return;
      activePointers.set(event.pointerId, control);
      syncPressedState(control);
      dispatchKeyboard("keydown", control);
    });
  }

  window.addEventListener("pointerup", releasePointer);
  window.addEventListener("pointercancel", releasePointer);
  window.addEventListener("blur", releaseAll);
}

function controlButton(
  control: TouchControl,
  label: string,
  text: string,
  className: string
): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.dataset.touchKey = control;
  button.dataset.pressed = "false";
  button.setAttribute("aria-label", label);
  button.textContent = text;
  return button;
}

function actionButton(): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "touch-action";
  button.dataset.touchKey = "E";
  button.dataset.contextual = "false";
  button.dataset.pressed = "false";
  button.setAttribute("aria-label", "Взаимодействовать");

  const key = document.createElement("span");
  key.className = "touch-action-key";
  key.textContent = "Действие";

  const context = document.createElement("span");
  context.className = "touch-action-context";
  context.textContent = DEFAULT_ACTION_CONTEXT;

  button.append(key, context);
  return button;
}

function bindActionContext(button: HTMLButtonElement): void {
  const hint = document.getElementById("interaction-hint");
  const context = button.querySelector<HTMLElement>(".touch-action-context");
  if (!hint || !context) return;

  hint.setAttribute("role", "status");
  hint.setAttribute("aria-live", "polite");
  hint.setAttribute("aria-atomic", "true");

  const sync = (): void => {
    const nextContext = actionContextFromHint(hint.textContent ?? "");
    context.textContent = nextContext;
    button.dataset.contextual = nextContext === DEFAULT_ACTION_CONTEXT ? "false" : "true";
    const isContextual = nextContext !== DEFAULT_ACTION_CONTEXT;
    hint.dataset.contextual = isContextual ? "true" : "false";
    hint.setAttribute("aria-label", isContextual ? `Доступно действие: ${nextContext}` : "Подсказка управления");
  };

  sync();
  new MutationObserver(sync).observe(hint, {
    childList: true,
    characterData: true,
    subtree: true
  });
}

function actionContextFromHint(hintText: string): string {
  const normalized = hintText.trim();
  if (!normalized.startsWith(TOUCH_ACTION_PREFIX)) return DEFAULT_ACTION_CONTEXT;
  const action = normalized.slice(TOUCH_ACTION_PREFIX.length).trim();
  return action || DEFAULT_ACTION_CONTEXT;
}

function releasePointer(event: PointerEvent): void {
  const control = activePointers.get(event.pointerId);
  if (!control) return;
  activePointers.delete(event.pointerId);
  syncPressedState(control);
  dispatchKeyboard("keyup", control);
}

function releaseAll(): void {
  const controls = new Set(activePointers.values());
  for (const control of activePointers.values()) dispatchKeyboard("keyup", control);
  activePointers.clear();
  for (const control of controls) syncPressedState(control);
}

function syncPressedState(control: TouchControl): void {
  const button = document.querySelector<HTMLButtonElement>(`#touch-controls button[data-touch-key="${control}"]`);
  if (!button) return;
  button.dataset.pressed = Array.from(activePointers.values()).includes(control) ? "true" : "false";
}

function dispatchKeyboard(type: "keydown" | "keyup", control: TouchControl): void {
  const spec = KEYS[control];
  const event = new KeyboardEvent(type, {
    key: spec.key,
    code: spec.code,
    bubbles: true,
    cancelable: true
  });
  Object.defineProperty(event, "keyCode", { get: () => spec.keyCode });
  Object.defineProperty(event, "which", { get: () => spec.keyCode });
  window.dispatchEvent(event);
}
