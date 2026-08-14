from __future__ import annotations

from .domain import ActionResult, WorldView


HELP_TEXT = (
    "Пока понимаю: `осмотреться`, `идти <location_id>`, "
    "`взять <entity_id>`, `положить <entity_id>`.\n"
    "Например: `идти village_square` или `взять stone_flat_1`."
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
    entity_lines = [
        f"- {entity.name} (`{entity.id}`)" for entity in view.entities
    ]
    actors = "\n".join(actor_lines) if actor_lines else "- никого"
    entities = "\n".join(entity_lines) if entity_lines else "- ничего заметного"
    return limit_message(
        f"## {view.location_name}\n"
        f"{view.location_description}\n\n"
        f"**Здесь:**\n{actors}\n\n"
        f"**Предметы:**\n{entities}"
    )


def render_me(view: WorldView) -> str:
    inventory_lines = [
        f"- {entity.name} (`{entity.id}`)" for entity in view.inventory
    ]
    inventory = "\n".join(inventory_lines) if inventory_lines else "- пусто"
    return limit_message(
        f"**Ты:** `{view.player_id}`\n"
        f"**Место:** {view.location_name} (`{view.location_id}`)\n\n"
        f"**Инвентарь:**\n{inventory}"
    )


def render_action_result(result: ActionResult) -> str:
    if result.success:
        return f"✅ {result.summary}"
    return f"⚠️ {result.summary} (`{result.code}`)"
