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

  const action = controlButton("E", "Взаимодействовать", "Действие", "touch-action");
  root.append(dpad, action);

  const dialogue = document.getElementById("dialogue");
  if (dialogue) app.insertBefore(root, dialogue);
  else app.append(root);

  for (const button of root.querySelectorAll<HTMLButtonElement>("button[data-touch-key]")) {
    button.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const control = button.dataset.touchKey as TouchControl | undefined;
      if (!control || activePointers.has(event.pointerId)) return;
      activePointers.set(event.pointerId, control);
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
  button.setAttribute("aria-label", label);
  button.textContent = text;
  return button;
}

function releasePointer(event: PointerEvent): void {
  const control = activePointers.get(event.pointerId);
  if (!control) return;
  activePointers.delete(event.pointerId);
  dispatchKeyboard("keyup", control);
}

function releaseAll(): void {
  for (const control of activePointers.values()) dispatchKeyboard("keyup", control);
  activePointers.clear();
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
