import Phaser from "phaser";

import { requestId } from "../api";
import {
  createProductionFirewood,
  createProductionPlayer,
  preloadVillageProductionArt,
  renderVillageProductionBackground,
  renderVillageProductionForeground
} from "../productionArt";
import { getRuntime } from "../runtime";

type Hotspot = { id: string; x: number; y: number; view: any };
type Rect = { x: number; y: number; w: number; h: number };
type VillageInteraction = { kind: "firewood"; item: Hotspot } | { kind: "tavern" };

export class VillageScene extends Phaser.Scene {
  private player: any;
  private keys: any;
  private hint!: HTMLElement;
  private firewood: Hotspot[] = [];
  private interaction: VillageInteraction | null = null;
  private interactionExpiresAt = 0;
  private readonly interactionGraceMs = 600;
  private readonly tavern = { x: 825, y: 250 };
  private readonly obstacles: Rect[] = [
    { x: 115, y: 205, w: 230, h: 120 },
    { x: 690, y: 165, w: 220, h: 135 },
    { x: 435, y: 330, w: 105, h: 90 }
  ];

  constructor() {
    super("VillageScene");
  }

  preload(): void {
    preloadVillageProductionArt(this);
  }

  create(): void {
    this.hint = document.getElementById("interaction-hint") as HTMLElement;
    const productionBackground = renderVillageProductionBackground(this);
    if (!productionBackground) this.drawWorld();
    this.createFirewood();
    this.player = createProductionPlayer(this, 430, 455)
      ?? this.add.rectangle(430, 455, 24, 42, 0xe03a3e).setStrokeStyle(4, 0x111315).setDepth(20);
    renderVillageProductionForeground(this);
    this.publishPlayerPosition();
    const keyboard = this.input.keyboard;
    if (!keyboard) throw new Error("Keyboard input unavailable");
    this.keys = keyboard.addKeys("W,A,S,D,E");
    keyboard.on("keydown-E", () => void this.interact());
    this.events.once("shutdown", () => {
      keyboard.removeAllListeners("keydown-E");
      this.clearInteraction();
      this.hint.textContent = "";
    });
  }

  update(_time: number, delta: number): void {
    // A long browser frame must not teleport the player through narrow collision/interaction bands.
    const speed = 0.22 * Math.min(delta, 50);
    let dx = 0;
    let dy = 0;
    if (this.keys.A.isDown) dx -= speed;
    if (this.keys.D.isDown) dx += speed;
    if (this.keys.W.isDown) dy -= speed;
    if (this.keys.S.isDown) dy += speed;
    this.movePlayer(dx, dy);
    this.publishPlayerPosition();
    this.updateHint();
  }

  private publishPlayerPosition(): void {
    document.body.dataset.playerX = Math.round(this.player.x).toString();
    document.body.dataset.playerY = Math.round(this.player.y).toString();
  }

  private drawWorld(): void {
    this.cameras.main.setBackgroundColor("#66d8dc");
    this.add.rectangle(480, 150, 960, 300, 0x66d8dc);
    this.add.triangle(160, 170, 0, 160, 180, 5, 330, 160, 0xe9e7df).setStrokeStyle(7, 0x303337);
    this.add.triangle(450, 150, 0, 180, 205, 0, 420, 180, 0xd8d8d1).setStrokeStyle(7, 0x34373a);
    this.add.triangle(790, 175, 0, 175, 170, 20, 355, 175, 0xf0eee7).setStrokeStyle(7, 0x33363a);
    this.add.rectangle(480, 382, 960, 316, 0x2e3134);
    this.add.polygon(480, 405, [0, 90, 960, 15, 960, 125, 0, 180], 0xdedbd2);

    this.add.rectangle(230, 264, 220, 118, 0xe9e6dc).setStrokeStyle(8, 0x222427);
    this.add.triangle(230, 190, 0, 70, 110, 0, 220, 70, 0x2b2d31);
    this.add.text(145, 250, "МАСТЕРСКАЯ", { color: "#232528", fontSize: "18px", fontFamily: "sans-serif" });

    this.add.rectangle(800, 235, 215, 135, 0xeeeae0).setStrokeStyle(8, 0x232528);
    this.add.triangle(800, 150, 0, 80, 108, 0, 216, 80, 0x292c2f);
    this.add.rectangle(825, 255, 48, 74, 0x25282b).setStrokeStyle(4, 0xe03a3e);
    this.add.text(733, 214, "ТАВЕРНА", { color: "#202326", fontSize: "22px", fontFamily: "sans-serif", fontStyle: "bold" });
    this.add.rectangle(758, 274, 32, 23, 0xe0a34c);

    this.add.ellipse(485, 360, 105, 42, 0x60d5d8).setStrokeStyle(6, 0x25282b);
    this.add.rectangle(485, 335, 75, 24, 0xe6e3d9).setStrokeStyle(5, 0x282a2d);
    this.add.text(443, 298, "КОЛОДЕЦ", { color: "#f0eee7", fontSize: "15px" });

    for (const x of [65, 115, 365, 600, 650, 920]) {
      this.add.ellipse(x, 386, 42, 78, 0x58615a).setStrokeStyle(4, 0x2b2e31);
    }
    this.add.text(24, 24, "СТАРТОВАЯ ДЕРЕВНЯ", { color: "#17191b", fontSize: "24px", fontStyle: "bold" });
    this.add.text(24, 55, "картонная диорама · playable greybox", { color: "#293136", fontSize: "15px" });
  }

  private createFirewood(): void {
    const snapshot = getRuntime().state.snapshot;
    const visible = snapshot?.world.visible_entities.filter((entity) => entity.entity_type === "firewood") ?? [];
    const positions = [
      [112, 430], [151, 446], [188, 428], [224, 449], [260, 431]
    ];
    this.firewood = visible.map((entity, index) => {
      const [x, y] = positions[index] ?? [110 + index * 38, 430];
      const productionView = createProductionFirewood(this, x, y);
      if (productionView) return { id: entity.entity_id, x, y, view: productionView };

      const body = this.add.rectangle(0, 0, 28, 12, 0xe9e4d7).setStrokeStyle(4, 0x24272a);
      const accent = this.add.rectangle(0, 0, 6, 16, 0xe03a3e);
      const label = this.add.text(-23, 15, `${index + 1}`, { color: "#f1eee4", fontSize: "12px" });
      const view = this.add.container(x, y, [body, accent, label]).setDepth(12);
      return { id: entity.entity_id, x, y, view };
    });
  }

  private movePlayer(dx: number, dy: number): void {
    const nx = Phaser.Math.Clamp(this.player.x + dx, 24, 936);
    const ny = Phaser.Math.Clamp(this.player.y + dy, 315, 510);
    if (!this.collides(nx, this.player.y)) this.player.x = nx;
    if (!this.collides(this.player.x, ny)) this.player.y = ny;
  }

  private collides(x: number, y: number): boolean {
    const halfW = 12;
    const halfH = 21;
    return this.obstacles.some((rect) =>
      x + halfW > rect.x && x - halfW < rect.x + rect.w && y + halfH > rect.y && y - halfH < rect.y + rect.h
    );
  }

  private updateHint(): void {
    const wood = this.nearestFirewood();
    if (wood) {
      this.offerInteraction({ kind: "firewood", item: wood }, "E — подобрать дрова");
      return;
    }
    if (distance(this.player.x, this.player.y, this.tavern.x, this.tavern.y) < 85) {
      this.offerInteraction({ kind: "tavern" }, "E — войти в таверну");
      return;
    }
    if (this.interaction && this.time.now <= this.interactionExpiresAt) return;
    this.clearInteraction();
    this.hint.textContent = "WASD — движение · E — взаимодействие";
  }

  private offerInteraction(interaction: VillageInteraction, text: string): void {
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
    if (interaction.kind === "firewood") {
      await this.pickupFirewood(interaction.item);
      return;
    }
    await this.enterTavern();
  }

  private nearestFirewood(): Hotspot | null {
    return this.firewood.find((item) => distance(this.player.x, this.player.y, item.x, item.y) < 52) ?? null;
  }

  private async pickupFirewood(item: Hotspot): Promise<void> {
    const runtime = getRuntime();
    try {
      await this.ensureWorkshopLocation();
      const result = await runtime.api.action({
        player_id: runtime.state.playerId,
        action_type: "TAKE",
        target_id: item.id,
        external_id: requestId(`take-${item.id}`)
      });
      if (!result.success) {
        this.hint.textContent = result.summary;
        return;
      }
      item.view.destroy();
      this.firewood = this.firewood.filter((candidate) => candidate !== item);
      await runtime.state.refresh();
      this.hint.textContent = "Дрова добавлены в канонический инвентарь";
    } catch (error) {
      this.hint.textContent = error instanceof Error ? error.message : "Ошибка взаимодействия";
    }
  }

  private async enterTavern(): Promise<void> {
    const runtime = getRuntime();
    try {
      const location = runtime.state.snapshot?.world.location_id;
      if (location === "workshop_yard") {
        await this.moveCanonical("village_square");
      } else if (location === "river_edge") {
        await this.moveCanonical("village_square");
      }
      if (runtime.state.snapshot?.world.location_id === "village_square") {
        await this.moveCanonical("tavern_interior");
      }
      if (runtime.state.snapshot?.world.location_id !== "tavern_interior") {
        throw new Error("Не удалось войти в таверну");
      }
      this.scene.start("TavernScene");
    } catch (error) {
      this.hint.textContent = error instanceof Error ? error.message : "Таверна недоступна";
    }
  }

  private async ensureWorkshopLocation(): Promise<void> {
    const runtime = getRuntime();
    const current = runtime.state.snapshot?.world.location_id;
    if (current === "tavern_interior") await this.moveCanonical("village_square");
    if (runtime.state.snapshot?.world.location_id === "village_square") await this.moveCanonical("workshop_yard");
    if (runtime.state.snapshot?.world.location_id !== "workshop_yard") {
      throw new Error("Сначала вернись к мастерской");
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

function distance(ax: number, ay: number, bx: number, by: number): number {
  return Math.hypot(ax - bx, ay - by);
}
