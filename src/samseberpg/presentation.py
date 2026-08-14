from __future__ import annotations

from .digest import WorldDigest
from .domain import ActionResult, WorldView
from .progression import ABILITIES, ACHIEVEMENTS


HELP_TEXT = (
    "Пока понимаю: `осмотреться`, `идти <location_id>`, "
    "`взять <entity_id>`, `положить <entity_id>`, "
    "`бросить <item_id> в <target_id>`, `дать <item_id> <actor_id>`, "
    "`купить <item_id> у <actor_id>`, `использовать <item_id> на <target_id>`, "
    "`говорить <npc_id>`, `сказать <npc_id> <текст>`.\n"
    "Например: `бросить stone_flat_1 в tavern_sign`; `сказать npc_mira привет`."
)


def limit_message(text: str, limit: int = 1900) -> str:
    if limit < 2:
        raise ValueError("limit must be at least 2")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def render_world(view: WorldView) -> str:
    actor_lines = [
        f"- **{actor.name}** (`{actor.id}`)"
        + (f" — {actor.activity}" if actor.activity else "")
        for actor in view.actors
    ]
    entity_lines = []
    for entity in view.entities:
        details = []
        condition = entity.state.get("condition")
        if isinstance(condition, int) and not isinstance(condition, bool):
            details.append(f"состояние: {condition}%")
        price = entity.state.get("price")
        if isinstance(price, int) and not isinstance(price, bool) and price > 0:
            details.append(f"цена: {price} монеты")
        state_suffix = f" — {', '.join(details)}" if details else ""
        entity_lines.append(f"- {entity.name} (`{entity.id}`){state_suffix}")
    actors = "\n".join(actor_lines) if actor_lines else "- никого"
    entities = "\n".join(entity_lines) if entity_lines else "- ничего заметного"
    exits = ", ".join(f"`{location_id}`" for location_id in view.exits) or "нет"
    return limit_message(
        f"## {view.location_name}\n"
        f"{view.location_description}\n\n"
        f"**Выходы:** {exits}\n\n"
        f"**Здесь:**\n{actors}\n\n"
        f"**Предметы:**\n{entities}"
    )


def render_me(view: WorldView) -> str:
    inventory_lines = []
    for entity in view.inventory:
        filled_with = entity.state.get("filled_with")
        state_suffix = f" — внутри: {filled_with}" if filled_with else ""
        inventory_lines.append(f"- {entity.name} (`{entity.id}`){state_suffix}")
    inventory = "\n".join(inventory_lines) if inventory_lines else "- пусто"
    achievement_lines = [
        f"- {ACHIEVEMENTS[code].name} (`{code}`)" if code in ACHIEVEMENTS else f"- `{code}`"
        for code in view.achievement_codes
    ]
    ability_lines = [
        f"- {ABILITIES[code].name} (`{code}`)" if code in ABILITIES else f"- `{code}`"
        for code in view.ability_codes
    ]
    achievements = "\n".join(achievement_lines) if achievement_lines else "- пока нет"
    abilities = "\n".join(ability_lines) if ability_lines else "- пока нет"
    return limit_message(
        f"**Ты:** `{view.player_id}`\n"
        f"**Место:** {view.location_name} (`{view.location_id}`)\n"
        f"**Монеты:** {view.coins}\n\n"
        f"**Инвентарь:**\n{inventory}\n\n"
        f"**Достижения:**\n{achievements}\n\n"
        f"**Навыки:**\n{abilities}"
    )


def render_action_result(result: ActionResult) -> str:
    if result.success:
        lines = [f"✅ {result.summary}"]
        for unlock in result.data.get("unlocks", []):
            if unlock.get("kind") == "achievement":
                lines.append(f"🏆 Открыто достижение: {unlock.get('name', unlock.get('code', ''))}")
            elif unlock.get("kind") == "ability":
                lines.append(f"✨ Новый навык: {unlock.get('name', unlock.get('code', ''))}")
        return "\n".join(lines)
    return f"⚠️ {result.summary} (`{result.code}`)"


def render_world_digest(digest: WorldDigest) -> str:
    event_lines = []
    for event in digest.events:
        stamp = event.occurred_at[11:16] if len(event.occurred_at) >= 16 else event.occurred_at
        location = f" в `{event.location_id}`" if event.location_id else ""
        event_lines.append(
            f"- {stamp} — **{event.actor_name}**: {event.summary}{location}"
        )
    if digest.omitted_event_count:
        event_lines.insert(0, f"- …ещё событий: {digest.omitted_event_count}")
    events = "\n".join(event_lines) if event_lines else "- заметных новых событий нет"

    damage_lines = [
        f"- {entity.name} (`{entity.id}`) — состояние: {entity.condition}%"
        for entity in digest.damaged_entities
    ]
    damage = "\n".join(damage_lines) if damage_lines else "- значимых повреждений нет"

    npc_lines = [
        f"- **{npc.name}** (`{npc.id}`) — `{npc.location_id}`; {npc.activity}"
        for npc in digest.npcs
    ]
    npcs = "\n".join(npc_lines) if npc_lines else "- никого"

    return limit_message(
        "# 📰 Деревенская сводка\n"
        f"После вашей последней активности (event `{digest.since_event_id}`).\n\n"
        f"**Что произошло:**\n{events}\n\n"
        f"**Состояние мира:**\n{damage}\n\n"
        f"**Где сейчас жители:**\n{npcs}"
    )
