import type { ActionResult, GameApi, GameSnapshot, LivingWorldEvent } from "../api";
import { requestId } from "../api";
import type { ClientState } from "../state";

type ActionInput = Parameters<GameApi["action"]>[0];
type PanelAction = Omit<ActionInput, "player_id">;

const LOCATION_LABELS: Record<string, string> = {
  workshop_yard: "мастерская",
  village_square: "площадь",
  river_edge: "река",
  tavern_interior: "таверна"
};

export class WorldPanel {
  private readonly root: HTMLElement;
  private busy = false;
  private lastResult = "";

  constructor(private readonly state: ClientState) {
    const root = document.getElementById("world-panel");
    if (!root) throw new Error("Панель Живого мира не найдена");
    this.root = root;
    state.subscribe((snapshot) => this.render(snapshot));
  }

  private render(snapshot: GameSnapshot): void {
    const living = snapshot.living_world;
    const hasDriftwood = snapshot.world.inventory.some((item) => item.entity_id === "driftwood_1");
    this.root.dataset.worldTick = String(living.tick);
    this.root.dataset.miraStatus = living.mira.status;
    this.root.dataset.miraWoodStock = String(living.mira.wood_stock);
    this.root.dataset.kasparStatus = living.kaspar.status;
    this.root.dataset.kasparCarrying = String(living.kaspar.carrying_wood);
    this.root.dataset.hasDriftwood = String(hasDriftwood);

    this.root.replaceChildren();

    const heading = document.createElement("div");
    heading.className = "world-panel-heading";
    const title = document.createElement("strong");
    title.textContent = "Живой мир";
    const tick = document.createElement("span");
    tick.textContent = `ход ${living.tick}`;
    heading.append(title, tick);

    const summary = document.createElement("div");
    summary.className = "world-summary";
    summary.append(
      this.statusRow(
        "Мира",
        living.mira.status === "needs_wood"
          ? `нужна древесина · запас ${living.mira.wood_stock}`
          : `работает · запас ${living.mira.wood_stock}`
      ),
      this.statusRow("Каспар", kasparStatusText(living.kaspar.status, living.kaspar.carrying_wood)),
      this.statusRow(
        "Ты",
        `${LOCATION_LABELS[snapshot.world.location_id] ?? snapshot.world.location_name.toLowerCase()}${hasDriftwood ? " · коряга у тебя" : ""}`
      )
    );

    const visible = document.createElement("div");
    visible.className = "world-visible";
    const actorNames = snapshot.world.visible_actors.map((actor) => actor.name).join(", ") || "никого";
    const entityNames = snapshot.world.visible_entities.map(displayEntityName).join(", ") || "ничего переносимого";
    visible.textContent = `Рядом: ${actorNames}. Предметы: ${entityNames}.`;

    const actions = document.createElement("div");
    actions.className = "world-actions";
    this.addLocationActions(actions, snapshot);
    this.addAction(actions, "Подождать 1 ход", {
      action_type: "WAIT",
      modifiers: { ticks: 1 },
      external_id: requestId("playtest-wait-1")
    });
    this.addAction(actions, "Подождать 4 хода", {
      action_type: "WAIT",
      modifiers: { ticks: 4 },
      external_id: requestId("playtest-wait-4")
    });

    const driftwoodVisible = snapshot.world.visible_entities.some((item) => item.entity_id === "driftwood_1");
    if (driftwoodVisible) {
      this.addAction(actions, "Забрать корягу", {
        action_type: "TAKE",
        target_id: "driftwood_1",
        external_id: requestId("playtest-take-driftwood")
      });
    }

    const miraVisible = snapshot.world.visible_actors.some((actor) => actor.actor_id === "npc_mira");
    if (hasDriftwood && miraVisible && living.mira.status === "needs_wood") {
      this.addAction(actions, "Отдать корягу Мире", {
        action_type: "GIVE",
        target_id: "driftwood_1",
        recipient_id: "npc_mira",
        external_id: requestId("playtest-give-driftwood")
      });
    }

    const events = document.createElement("div");
    events.className = "world-events";
    const eventTitle = document.createElement("span");
    eventTitle.className = "world-events-title";
    eventTitle.textContent = "Последние события";
    events.append(eventTitle);
    const recent = living.recent_events.slice(-4).reverse();
    if (recent.length === 0) {
      const empty = document.createElement("div");
      empty.textContent = "Мир пока спокоен.";
      events.append(empty);
    } else {
      for (const event of recent) {
        const line = document.createElement("div");
        line.textContent = `• ${eventText(event)}`;
        events.append(line);
      }
    }

    const result = document.createElement("div");
    result.className = "world-result";
    result.setAttribute("aria-live", "polite");
    result.textContent = this.lastResult || "Наблюдай за Мирой и Каспаром — их действия меняются даже без твоей помощи.";

    this.root.append(heading, summary, visible, actions, events, result);
  }

  private statusRow(name: string, status: string): HTMLElement {
    const row = document.createElement("div");
    row.className = "world-status-row";
    const label = document.createElement("span");
    label.textContent = name;
    const value = document.createElement("span");
    value.textContent = status;
    row.append(label, value);
    return row;
  }

  private addLocationActions(container: HTMLElement, snapshot: GameSnapshot): void {
    const current = snapshot.world.location_id;
    if (current === "workshop_yard") {
      this.addMove(container, "На площадь", "village_square");
      return;
    }
    if (current === "village_square") {
      this.addMove(container, "К мастерской", "workshop_yard");
      this.addMove(container, "К реке", "river_edge");
      return;
    }
    if (current === "river_edge") {
      this.addMove(container, "На площадь", "village_square");
    }
  }

  private addMove(container: HTMLElement, label: string, destination: string): void {
    this.addAction(container, label, {
      action_type: "MOVE",
      destination_id: destination,
      external_id: requestId(`playtest-move-${destination}`)
    });
  }

  private addAction(container: HTMLElement, label: string, action: PanelAction): void {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.disabled = this.busy;
    button.addEventListener("click", () => void this.execute(action));
    container.append(button);
  }

  private async execute(action: PanelAction): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    if (this.state.snapshot) this.render(this.state.snapshot);
    try {
      const result = await this.state.api.action({
        player_id: this.state.playerId,
        ...action
      });
      this.lastResult = actionResultText(action.action_type, result);
      await this.state.refresh();
    } catch (error) {
      this.lastResult = error instanceof Error ? error.message : "Действие не выполнено";
    } finally {
      this.busy = false;
      if (this.state.snapshot) this.render(this.state.snapshot);
    }
  }
}

function kasparStatusText(status: GameSnapshot["living_world"]["kaspar"]["status"], carrying: boolean): string {
  if (status === "collecting_wood") return "идёт за древесиной";
  if (status === "delivering_wood" || carrying) return "несёт древесину Мире";
  return "занят по расписанию";
}

function displayEntityName(entity: GameSnapshot["world"]["visible_entities"][number]): string {
  if (entity.entity_id === "driftwood_1") return "коряга";
  if (entity.entity_type === "firewood") return "дрова";
  return entity.name;
}

function eventText(event: LivingWorldEvent): string {
  switch (event.event_type) {
    case "NPC_WORKED":
      return "Мира закончила рабочий цикл.";
    case "NPC_REQUESTED_RESOURCE":
      return "Мире понадобилась древесина.";
    case "NPC_MOVED":
      return event.actor_id === "npc_kaspar"
        ? `Каспар переместился: ${LOCATION_LABELS[event.location_id ?? ""] ?? "другая часть деревни"}.`
        : "Кто-то из жителей сменил место.";
    case "NPC_COLLECTED_RESOURCE":
      return "Каспар забрал корягу у реки.";
    case "NPC_DELIVERED_RESOURCE":
      return "Каспар принёс древесину Мире.";
    default:
      return "В деревне что-то изменилось.";
  }
}

function actionResultText(actionType: PanelAction["action_type"], result: ActionResult): string {
  if (!result.success) return result.summary;
  if (actionType === "WAIT") return "Прошло немного времени. Посмотри, что изменилось.";
  if (actionType === "MOVE") return "Ты перешёл в другую часть деревни.";
  if (actionType === "TAKE") return "Коряга теперь у тебя.";
  if (actionType === "GIVE") return "Ты отдал корягу Мире — ситуация изменилась.";
  return result.summary;
}
