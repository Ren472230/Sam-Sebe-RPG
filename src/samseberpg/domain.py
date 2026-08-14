from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    LOOK = "LOOK"
    MOVE = "MOVE"
    TAKE = "TAKE"
    DROP = "DROP"
    THROW = "THROW"
    GIVE = "GIVE"
    BUY = "BUY"
    USE = "USE"
    TALK = "TALK"


@dataclass(frozen=True, slots=True)
class CanonicalAction:
    actor_id: str
    action_type: ActionType
    target_id: str | None = None
    item_id: str | None = None
    destination_id: str | None = None
    source_text: str | None = None


@dataclass(frozen=True, slots=True)
class ActionResult:
    success: bool
    code: str
    summary: str
    event_id: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class VisibleActor:
    id: str
    name: str
    actor_type: str
    activity: str | None = None


@dataclass(frozen=True, slots=True)
class VisibleEntity:
    id: str
    name: str
    entity_type: str
    portable: bool
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorldView:
    player_id: str
    coins: int
    location_id: str
    location_name: str
    location_description: str
    exits: tuple[str, ...]
    actors: tuple[VisibleActor, ...]
    entities: tuple[VisibleEntity, ...]
    inventory: tuple[VisibleEntity, ...]
    achievement_codes: tuple[str, ...] = ()
    ability_codes: tuple[str, ...] = ()
