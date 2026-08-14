from __future__ import annotations

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
        f"- {ACHIEVEMENTS[code].name} (`{code}`)"
        if code in ACHIEVEMENTS
        else f"- `{code}`"
        for code in view.achievement_codes
    ]
    ability_lines = [
        f"- {ABILITIES[code].name} (`{code}`)"
        if code in ABILITIES
        else f"- `{code}`"
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
