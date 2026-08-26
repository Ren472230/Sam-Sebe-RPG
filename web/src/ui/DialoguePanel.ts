import type { DialogueDecision, QuestResult } from "../api";
import type { ClientState } from "../state";

export class DialoguePanel {
  private readonly root: HTMLElement;

  constructor(private readonly state: ClientState) {
    const root = document.getElementById("dialogue");
    if (!root) throw new Error("#dialogue not found");
    this.root = root;
  }

  async openOren(userText = "Привет. Есть работа?"): Promise<void> {
    this.showMessage("Орен", "...");
    try {
      const decision = await this.state.api.dialogue(this.state.playerId, userText);
      await this.state.refresh();
      this.renderDecision(decision);
    } catch (error) {
      this.showMessage("Связь с миром", readableError(error), [
        this.button("Повторить", () => void this.openOren(userText)),
        this.button("Закрыть", () => this.close())
      ]);
    }
  }

  close(): void {
    this.root.hidden = true;
    this.root.replaceChildren();
  }

  private renderDecision(decision: DialogueDecision): void {
    const snapshot = this.state.snapshot;
    if (!snapshot) return;
    const actions: HTMLButtonElement[] = [];

    if (snapshot.quest.status === "available") {
      actions.push(this.button("Взяться за дрова", () => void this.acceptQuest()));
    }
    if (snapshot.quest.status === "active") {
      actions.push(this.button("Передать дрова", () => void this.turnInQuest()));
    }
    actions.push(this.button("Закрыть", () => this.close()));

    const proposalMeta = decision.proposal === "offer_quest:bring_5_firewood" ? " · предложение квеста" : "";
    this.showMessage(
      "Орен",
      decision.text,
      actions,
      `${decision.used_fallback ? "локальная реплика" : "AI-реплика"}${proposalMeta}`
    );
  }

  private async acceptQuest(): Promise<void> {
    try {
      const result = await this.state.api.acceptQuest(this.state.playerId);
      await this.state.refresh();
      if (!result.success) {
        this.showResult(result);
        return;
      }
      await this.openOren("Я возьмусь. Напомни, сколько нужно?");
    } catch (error) {
      this.showMessage("Система", readableError(error), [this.button("Закрыть", () => this.close())]);
    }
  }

  private async turnInQuest(): Promise<void> {
    try {
      const result = await this.state.api.turnInQuest(this.state.playerId);
      await this.state.refresh();
      if (!result.success) {
        this.showResult(result);
        return;
      }
      await this.openOren("Вот дрова.");
    } catch (error) {
      this.showMessage("Система", readableError(error), [this.button("Закрыть", () => this.close())]);
    }
  }

  private showResult(result: QuestResult): void {
    this.showMessage("Система", result.summary, [
      this.button("Снова к Орену", () => void this.openOren("Ну что?")),
      this.button("Закрыть", () => this.close())
    ]);
  }

  private showMessage(
    speaker: string,
    text: string,
    actions: HTMLButtonElement[] = [],
    meta?: string
  ): void {
    const title = document.createElement("h2");
    title.textContent = speaker;
    const copy = document.createElement("p");
    copy.textContent = text;
    const controls = document.createElement("div");
    controls.className = "dialogue-actions";
    controls.append(...actions);
    const elements: Node[] = [title, copy];
    if (meta) {
      const label = document.createElement("small");
      label.textContent = meta;
      elements.push(label);
    }
    elements.push(controls);
    this.root.replaceChildren(...elements);
    this.root.hidden = false;
  }

  private button(label: string, onClick: () => void): HTMLButtonElement {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }
}

function readableError(error: unknown): string {
  return error instanceof Error ? error.message : "Неизвестная ошибка";
}
