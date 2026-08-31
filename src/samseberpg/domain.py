from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    LOOK = "LOOK"
    MOVE = "MOVE"
    TAKE = "TAKE"
    DROP = "DROP"
    GIVE = "GIVE"
    WAIT = "WAIT"


@dataclass(frozen=True, slots=True)
class CanonicalAction:
    actor_id: str
    action_type: ActionType
    target_id: str | None = None
    recipient_id: str | None = None
    destination_id: str | None = None
    source_text: str | None = None
    modifiers: dict[str, int] | None = None


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


@dataclass(frozen=True, slots=True)
class QuestState:
    quest_type: str
    status: str
    required_firewood: int
    owned_firewood: int


@dataclass(frozen=True, slots=True)
class QuestResult:
    success: bool
    code: str
    summary: str
    state: QuestState
    event_id: int | None = None
    replayed: bool = False
