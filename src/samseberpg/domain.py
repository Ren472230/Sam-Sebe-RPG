from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    LOOK = "LOOK"
    MOVE = "MOVE"
    TAKE = "TAKE"
    DROP = "DROP"
    THROW = "THROW"


class MechanicPrimitive(str, Enum):
    MODIFY_ACCURACY = "MODIFY_ACCURACY"
    MODIFY_RANGE = "MODIFY_RANGE"
    MODIFY_COST = "MODIFY_COST"
    MODIFY_QUALITY = "MODIFY_QUALITY"
    MODIFY_RELATION_GAIN = "MODIFY_RELATION_GAIN"
    UNLOCK_ACTION_VARIANT = "UNLOCK_ACTION_VARIANT"
    CONDITIONAL_MODIFIER = "CONDITIONAL_MODIFIER"
    REPUTATION_TAG = "REPUTATION_TAG"


@dataclass(frozen=True, slots=True)
class MechanicSpec:
    mechanic_id: str
    primitive: MechanicPrimitive | str
    magnitude: object | None = None


@dataclass(frozen=True, slots=True)
class CanonicalAction:
    actor_id: str
    action_type: ActionType
    target_id: str | None = None
    item_id: str | None = None
    destination_id: str | None = None
    modifiers: dict[str, object] | None = None
    source_text: str | None = None


@dataclass(frozen=True, slots=True)
class VisibleActor:
    actor_id: str
    name: str
    actor_type: str


@dataclass(frozen=True, slots=True)
class VisibleEntity:
    entity_id: str
    name: str
    entity_type: str
    portable: bool


@dataclass(frozen=True, slots=True)
class WorldView:
    player_id: str
    location_id: str
    location_name: str
    location_description: str
    visible_actors: tuple[VisibleActor, ...] = ()
    visible_entities: tuple[VisibleEntity, ...] = ()
    inventory: tuple[VisibleEntity, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionResult:
    success: bool
    code: str
    summary: str
    event_id: int | None = None
    replayed: bool = False
