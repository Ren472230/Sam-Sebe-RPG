import Phaser from "phaser";

import { requestId, type VisibleActor } from "../api";
import { actionControlHint, movementControlHint } from "../controlHints";
import {
  createProductionOren,
  createProductionPlayer,
  preloadTavernProductionArt,
  renderTavernProductionBackground,
  renderTavernProductionForeground
} from "../productionArt";
import { getRuntime } from "../runtime";

type TavernInteraction =
  | { kind: "npc"; actorId: string; name: string }
  | { kind: "exit" };

type VisitorView = { actor: VisibleActor; view: Phaser.GameObjects.Container };

const VISITOR_ANCHORS: Record<string, { x: number; y: number }> = {
  npc_wayfarer_1: { x: 500, y: 385 }
};

export class TavernScene extends Phaser.Scene {
  private player: any;
  private keys: any;
  private hint!: HTMLElement;
  private interaction: TavernInteraction | null = null;
  private interactionExpiresAt = 0;
  private readonly interactionGraceMs = 600;
  private readonly oren = { x: 650, y: 325 };
  private readonly exit = { x: 110, y: 420 };
  private readonly visitors = new Map<string, VisitorView>();
  private unsubscribeState: (() => void) | null = null;

  constructor() {
    super("TavernScene");
  }

  preload(): void {
    preloadTavernProductionArt(this);
  }

  create(): void {
    this.hint = document.getElementById("interaction-hint") as HTMLElement;
    const productionBackground = renderTavernProductionBackground(this);
    if (!productionBackground) this.drawGreyboxWorld();

    const productionOren = createProductionOren(this, this.oren.x, this.oren.y);
    if (!productionOren) {
      this.add.rectangle(650, 325, 38, 68, 0x2b2e31).setStrokeStyle(5, 0xe03a3e).setDepth(18);
      this.add.text(624, 365, "ОРЕН", { color: "#1f2225", fontSize: "17px", fontStyle: "bold" }).setDepth(18);
    }

    this.player = createProductionPlayer(this, 270, 425)
      ?? this.add.rectangle(270, 425, 24, 42, 0xe03a3e).setStrokeStyle(4, 0x111315).setDepth(20);
    renderTavernProductionForeground(this);
    this.publishPlayerPosition();

    const runtime = getRuntime();
    this.unsubscribeState = runtime.state.subscribe((snapshot) => {
      this.renderVisibleVisitors(snapshot.world.visible_actors);
    });

    const keyboard = this.input.keyboard;
    if (!keyboard) throw new Error("Keyboard input unavailable");
    this.keys = keyboard.addKeys("W,A,S,D,E", false);
    keyboard.on("keydown-E", (event: KeyboardEvent) => {
      if (event.repeat || isTextEntryActive()) return;
      void this.interact();
    });
    this.events.once("shutdown", () => {
      this.unsubscribeState?.();
      this.unsubscribeState = null;
      this.destroyVisitors();
      this.clearInteraction();
      this.hint.textContent = "";
    });
  }

  update(_time: number, delta: number): void {
    if (isTextEntryActive()) return;

    const speed = 0.22 * Math.min(delta, 50);
    let dx = 0;
    let dy = 0;
    if (this.keys.A.isDown) dx -= speed;
    if (this.keys.D.isDown) dx += speed;
    if (this.keys.W.isDown) dy -= speed;
    if (this.keys.S.isDown) dy += speed;
    this.player.x = Phaser.Math.Clamp(this.player.x + dx, 80, 880);
    this.player.y = Phaser.Math.Clamp(this.player.y + dy, 315, 470);
    this.publishPlayerPosition();

    const visitor = this.nearestVisitor();
    if (visitor) {
      const name = npcName(visitor.actor_id, visitor.name);
      this.offerInteraction(
        { kind: "npc", actorId: visitor.actor_id, name },
        actionControlHint(`поговорить с ${npcInstrumentalName(visitor.actor_id, visitor.name)}`)
      );
    } else if (distance(this.player.x, this.player.y, this.oren.x, this.oren.y) < 85) {
      this.offerInteraction(
        { kind: "npc", actorId: "npc_oren", name: "Орен" },
        actionControlHint("поговорить с Ореном")
      );
    } else if (distance(this.player.x, this.player.y, this.exit.x, this.exit.y) < 70) {
      this.offerInteraction({ kind: "exit" }, actionControlHint("выйти в деревню"));
    } else if (this.interaction && this.time.now <= this.interactionExpiresAt) {
      return;
    } else {
      this.clearInteraction();
      this.hint.textContent = movementControlHint();
    }
  }

  private renderVisibleVisitors(visible_actors: VisibleActor[]): void {
    const visitors = visible_actors.filter(
      (actor) => actor.actor_type === "npc" && actor.actor_id !== "npc_oren"
    );
    const nextIds = new Set(visitors.map((actor) => actor.actor_id));

    for (const [actorId, current] of this.visitors) {
      if (nextIds.has(actorId)) continue;
      current.view.destroy(true);
      this.visitors.delete(actorId);
    }

    visitors.forEach((actor, index) => {
      const current = this.visitors.get(actor.actor_id);
      if (current) {
        current.actor = actor;
        return;
      }
      const anchor = VISITOR_ANCHORS[actor.actor_id] ?? { x: 450 + index * 70, y: 390 };
      const body = this.add.rectangle(0, 0, 30, 50, 0xe9e4d7)
        .setStrokeStyle(4, 0x24272a);
      const accent = this.add.rectangle(0, -20, 30, 7, 0xe0a34c);
      const label = this.add.text(-34, 32, npcName(actor.actor_id, actor.name), {
        color: "#f1eee4",
        backgroundColor: "#24272a",
        fontSize: "14px",
        fontFamily: "sans-serif",
        padding: { x: 4, y: 2 }
      });
      const view = this.add.container(anchor.x, anchor.y, [body, accent, label]).setDepth(19);
      this.visitors.set(actor.actor_id, { actor, view });
    });

    const rendered = ["npc_oren", ...this.visitors.keys()].sort();
    document.body.dataset.renderedTavernNpcIds = rendered.join(",");
  }

  private destroyVisitors(): void {
    for (const current of this.visitors.values()) current.view.destroy(true);
    this.visitors.clear();
    delete document.body.dataset.renderedTavernNpcIds;
  }

  private nearestVisitor(): VisibleActor | null {
    let best: { actor: VisibleActor; distance: number } | null = null;
    for (const { actor, view } of this.visitors.values()) {
      const gap = distance(this.player.x, this.player.y, view.x, view.y);
      if (gap >= 78 || (best && best.distance <= gap)) continue;
      best = { actor, distance: gap };
    }
    return best?.actor ?? null;
  }

  private drawGreyboxWorld(): void {
    this.cameras.main.setBackgroundColor("#24272a");
    this.add.rectangle(480, 270, 960, 540, 0x26292c);
    this.add.rectangle(480, 375, 900, 250, 0xe7e2d7).setStrokeStyle(10, 0x1d2023);
    this.add.rectangle(690, 270, 370, 72, 0x2b2e31).setStrokeStyle(5, 0x111315);
    this.add.rectangle(710, 185, 150, 110, 0xe0a34c).setStrokeStyle(10, 0x292c2f);
    this.add.rectangle(710, 195, 92, 72, 0x5b2f2a);
    this.add.text(645, 125, "ОЧАГ", { color: "#eee8dc", fontSize: "18px" });
    this.add.rectangle(110, 420, 58, 104, 0x25282b).setStrokeStyle(5, 0x64d5d9);
    this.add.text(70, 478, "ВЫХОД", { color: "#202326", fontSize: "15px" });
    this.add.text(28, 28, "ТАВЕРНА · ПУТНИЧИЙ ОЧАГ", { color: "#efe9dc", fontSize: "24px", fontStyle: "bold" });
  }

  private publishPlayerPosition(): void {
    document.body.dataset.playerX = Math.round(this.player.x).toString();
    document.body.dataset.playerY = Math.round(this.player.y).toString();
  }

  private offerInteraction(interaction: TavernInteraction, text: string): void {
    this.interaction = interaction;
    this.interactionExpiresAt = this.time.now + this.interactionGraceMs;
    this.hint.textContent = text;
  }

  private clearInteraction(): void {
    this.interaction = null;
    this.interactionExpiresAt = 0;
  }

  private async interact(): Promise<void> {
    const interaction = this.interaction;
    if (!interaction || this.time.now > this.interactionExpiresAt) {
      this.clearInteraction();
      return;
    }
    this.clearInteraction();
    if (interaction.kind === "npc") {
      await getRuntime().dialogue.openNpc(interaction.actorId);
      return;
    }
    await this.leaveTavern();
  }

  private async leaveTavern(): Promise<void> {
    const runtime = getRuntime();
    try {
      await this.moveCanonical("village_square");
      await this.moveCanonical("workshop_yard");
      runtime.dialogue.close();
      this.scene.start("VillageScene");
    } catch (error) {
      this.hint.textContent = error instanceof Error ? error.message : "Не удалось выйти";
    }
  }

  private async moveCanonical(destination: string): Promise<void> {
    const runtime = getRuntime();
    const result = await runtime.api.action({
      player_id: runtime.state.playerId,
      action_type: "MOVE",
      destination_id: destination,
      external_id: requestId(`move-${destination}`)
    });
    if (!result.success) throw new Error(result.summary);
    await runtime.state.refresh();
  }
}

function npcName(actorId: string, fallback: string): string {
  if (actorId === "npc_mira") return "Мира";
  if (actorId === "npc_kaspar") return "Каспар";
  if (actorId === "npc_wayfarer_1") return "Тален";
  if (actorId === "npc_oren") return "Орен";
  return fallback;
}

function npcInstrumentalName(actorId: string, fallback: string): string {
  if (actorId === "npc_mira") return "Мирой";
  if (actorId === "npc_kaspar") return "Каспаром";
  if (actorId === "npc_wayfarer_1") return "Таленом";
  if (actorId === "npc_oren") return "Ореном";
  return fallback;
}

function isTextEntryActive(): boolean {
  const dialogue = document.getElementById("dialogue");
  if (dialogue && !dialogue.hidden) return true;
  const active = document.activeElement;
  return active instanceof HTMLInputElement
    || active instanceof HTMLTextAreaElement
    || (active instanceof HTMLElement && active.isContentEditable);
}

function distance(ax: number, ay: number, bx: number, by: number): number {
  return Math.hypot(ax - bx, ay - by);
}