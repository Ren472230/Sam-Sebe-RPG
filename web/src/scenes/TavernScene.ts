import Phaser from "phaser";

import { requestId } from "../api";
import { getRuntime } from "../runtime";

export class TavernScene extends Phaser.Scene {
  private player: any;
  private keys: any;
  private hint!: HTMLElement;
  private readonly oren = { x: 650, y: 325 };
  private readonly exit = { x: 110, y: 420 };

  constructor() {
    super("TavernScene");
  }

  create(): void {
    this.hint = document.getElementById("interaction-hint") as HTMLElement;
    this.cameras.main.setBackgroundColor("#24272a");
    this.add.rectangle(480, 270, 960, 540, 0x26292c);
    this.add.rectangle(480, 375, 900, 250, 0xe7e2d7).setStrokeStyle(10, 0x1d2023);
    this.add.rectangle(690, 270, 370, 72, 0x2b2e31).setStrokeStyle(5, 0x111315);
    this.add.rectangle(710, 185, 150, 110, 0xe0a34c).setStrokeStyle(10, 0x292c2f);
    this.add.rectangle(710, 195, 92, 72, 0x5b2f2a);
    this.add.text(645, 125, "ОЧАГ", { color: "#eee8dc", fontSize: "18px" });
    this.add.rectangle(650, 325, 38, 68, 0x2b2e31).setStrokeStyle(5, 0xe03a3e);
    this.add.text(624, 365, "ОРЕН", { color: "#1f2225", fontSize: "17px", fontStyle: "bold" });
    this.add.rectangle(110, 420, 58, 104, 0x25282b).setStrokeStyle(5, 0x64d5d9);
    this.add.text(70, 478, "ВЫХОД", { color: "#202326", fontSize: "15px" });
    this.add.text(28, 28, "ТАВЕРНА · ПУТНИЧИЙ ОЧАГ", { color: "#efe9dc", fontSize: "24px", fontStyle: "bold" });

    this.player = this.add.rectangle(270, 425, 24, 42, 0xe03a3e).setStrokeStyle(4, 0x111315);
    this.keys = this.input.keyboard.addKeys("W,A,S,D,E");
    this.input.keyboard.on("keydown-E", () => void this.interact());
    this.events.once("shutdown", () => {
      this.input.keyboard.removeAllListeners("keydown-E");
      this.hint.textContent = "";
    });
  }

  update(_time: number, delta: number): void {
    const speed = 0.22 * delta;
    let dx = 0;
    let dy = 0;
    if (this.keys.A.isDown) dx -= speed;
    if (this.keys.D.isDown) dx += speed;
    if (this.keys.W.isDown) dy -= speed;
    if (this.keys.S.isDown) dy += speed;
    this.player.x = Phaser.Math.Clamp(this.player.x + dx, 80, 880);
    this.player.y = Phaser.Math.Clamp(this.player.y + dy, 315, 470);

    if (distance(this.player.x, this.player.y, this.oren.x, this.oren.y) < 85) {
      this.hint.textContent = "E — поговорить с Ореном";
    } else if (distance(this.player.x, this.player.y, this.exit.x, this.exit.y) < 70) {
      this.hint.textContent = "E — выйти в деревню";
    } else {
      this.hint.textContent = "WASD — движение · E — взаимодействие";
    }
  }

  private async interact(): Promise<void> {
    if (distance(this.player.x, this.player.y, this.oren.x, this.oren.y) < 85) {
      await getRuntime().dialogue.openOren();
      return;
    }
    if (distance(this.player.x, this.player.y, this.exit.x, this.exit.y) < 70) {
      await this.leaveTavern();
    }
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

function distance(ax: number, ay: number, bx: number, by: number): number {
  return Math.hypot(ax - bx, ay - by);
}
