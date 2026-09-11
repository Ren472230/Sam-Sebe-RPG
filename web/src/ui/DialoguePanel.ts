import type { QuestResult } from "../api";
import { dialogueResultEvidence } from "../playtestClient";
import type { ClientState } from "../state";
import { captureTelemetry } from "../telemetry";

type TranscriptLine = { speaker: "player" | "npc" | "quest" | "system"; text: string };

export class DialoguePanel {
  private readonly root: HTMLElement;
  private npcId = "npc_oren";
  private transcript: TranscriptLine[] = [];
  private sending = false;
  private dialogueTracked = false;

  constructor(private readonly state: ClientState) {
    const root = document.getElementById("dialogue");
    if (!root) throw new Error("#dialogue not found");
    this.root = root;
  }

  async openNpc(npcId: string, initialText?: string): Promise<void> {
    this.npcId = npcId;
    this.transcript = [];
    this.dialogueTracked = false;
    this.root.hidden = false;
    this.render();
    if (initialText?.trim()) await this.send(initialText.trim());
  }

  async openOren(): Promise<void> {
    await this.openNpc("npc_oren");
  }

  close(): void {
    this.root.hidden = true;
    this.root.replaceChildren();
    this.transcript = [];
  }

  private async send(text: string): Promise<void> {
    const clean = text.trim();
    if (!clean || this.sending) return;
    this.sending = true;
    this.transcript.push({ speaker: "player", text: clean });
    this.render();
    try {
      const decision = await this.state.api.dialogue(
        this.state.playerId,
        this.npcId,
        clean
      );
      if (!this.dialogueTracked) {
        captureTelemetry("npc_dialogue_started", {
          location_id: this.state.snapshot?.world.location_id,
          npc_id: this.npcId,
          dialogue_provider: decision.used_fallback ? "fallback" : "openai"
        });
        this.dialogueTracked = true;
      }
      document.dispatchEvent(new CustomEvent("samseberpg:dialogue-result", {
        detail: dialogueResultEvidence(this.npcId, decision.used_fallback)
      }));
      await this.state.refresh();
      this.transcript.push({ speaker: "npc", text: decision.text });
    } catch (error) {
      captureTelemetry("client_error", {
        location_id: this.state.snapshot?.world.location_id,
        npc_id: this.npcId
      });
      this.transcript.push({ speaker: "system", text: readableError(error) });
    } finally {
      this.sending = false;
      this.render();
    }
  }

  private render(): void {
    const title = document.createElement("h2");
    title.textContent = npcName(this.npcId);

    const transcript = document.createElement("div");
    transcript.className = "dialogue-transcript";
    if (this.transcript.length === 0) {
      const empty = document.createElement("p");
      empty.className = "dialogue-empty";
      empty.textContent = `Ты рядом с ${npcName(this.npcId)}. Скажи что-нибудь своими словами.`;
      transcript.append(empty);
    } else {
      for (const line of this.transcript) {
        const item = document.createElement("p");
        const visualSpeaker = line.speaker === "quest" ? "system" : line.speaker;
        item.className = `dialogue-line dialogue-line-${visualSpeaker}`;
        const prefix = line.speaker === "player"
          ? "Ты"
          : line.speaker === "npc"
            ? npcName(this.npcId)
            : line.speaker === "quest"
              ? "Задание"
              : "Система";
        item.textContent = `${prefix}: ${line.text}`;
        transcript.append(item);
      }
    }

    const input = document.createElement("textarea");
    input.className = "dialogue-input";
    input.rows = 2;
    input.placeholder = `Сказать ${npcName(this.npcId)}…`;
    input.disabled = this.sending;
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        void this.send(input.value);
      }
    });

    const send = this.button(
      this.sending ? "…" : "Отправить",
      () => void this.send(input.value)
    );
    send.disabled = this.sending;
    const controls = document.createElement("div");
    controls.className = "dialogue-actions";
    controls.append(send);

    const snapshot = this.state.snapshot;
    if (this.npcId === "npc_oren" && snapshot) {
      if (snapshot.quest.status === "available") {
        controls.append(
          this.button("Взяться за дрова", () => void this.acceptQuest())
        );
      } else if (snapshot.quest.status === "active") {
        controls.append(
          this.button("Передать дрова", () => void this.turnInQuest())
        );
      }
    }
    controls.append(this.button("Закрыть", () => this.close()));

    this.root.replaceChildren(title, transcript, input, controls);
    this.root.hidden = false;
    if (!this.sending) input.focus();
  }

  private async acceptQuest(): Promise<void> {
    try {
      const result = await this.state.api.acceptQuest(this.state.playerId);
      await this.state.refresh();
      if (!result.success) return this.showResult(result);
      captureTelemetry("quest_accepted", {
        location_id: this.state.snapshot?.world.location_id,
        npc_id: this.npcId,
        quest_id: result.state.quest_type
      });
      await this.send("Я возьмусь. Напомни, сколько нужно?");
    } catch (error) {
      captureTelemetry("client_error", {
        location_id: this.state.snapshot?.world.location_id,
        npc_id: this.npcId
      });
      this.transcript.push({ speaker: "system", text: readableError(error) });
      this.render();
    }
  }

  private async turnInQuest(): Promise<void> {
    try {
      const result = await this.state.api.turnInQuest(this.state.playerId);
      await this.state.refresh();
      if (!result.success) return this.showResult(result);
      captureTelemetry("quest_completed", {
        location_id: this.state.snapshot?.world.location_id,
        npc_id: this.npcId,
        quest_id: result.state.quest_type
      });
      await this.send("Вот дрова.");
    } catch (error) {
      captureTelemetry("client_error", {
        location_id: this.state.snapshot?.world.location_id,
        npc_id: this.npcId
      });
      this.transcript.push({ speaker: "system", text: readableError(error) });
      this.render();
    }
  }

  private showResult(result: QuestResult): void {
    this.transcript.push({ speaker: "quest", text: result.summary });
    this.render();
  }

  private button(label: string, onClick: () => void): HTMLButtonElement {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }
}

function npcName(npcId: string): string {
  if (npcId === "npc_mira") return "Мира";
  if (npcId === "npc_kaspar") return "Каспар";
  if (npcId === "npc_oren") return "Орен";
  if (npcId === "npc_wayfarer_1") return "Тален";
  return npcId;
}

function readableError(error: unknown): string {
  return error instanceof Error ? error.message : "Неизвестная ошибка";
}
