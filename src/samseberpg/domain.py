from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(str, Enum):
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
    destination_id: str | None = None
    source_text: str | None = None
    item_id: str | None = None


@dataclass(frozen=True, slots=True)
class VisibleActor:
    actor_id: str
    name: str
    actor_type: str
    activity: str | None = None

    @property
    def id(self) -> str:
        """Founder-build alias that keeps the shared-kernel field authoritative."""
        return self.actor_id


@dataclass(frozen=True, slots=True)
class VisibleEntity:
    entity_id: str
    name: str
    entity_type: str
    portable: bool
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Founder-build alias that keeps the shared-kernel field authoritative."""
        return self.entity_id


@dataclass(frozen=True, slots=True)
class WorldView:
    player_id: str
    location_id: str
    location_name: str
    location_description: str
    visible_actors: tuple[VisibleActor, ...] = ()
    visible_entities: tuple[VisibleEntity, ...] = ()
    inventory: tuple[VisibleEntity, ...] = ()
    coins: int = 0
    exits: tuple[str, ...] = ()
    achievement_codes: tuple[str, ...] = ()
    ability_codes: tuple[str, ...] = ()

    @property
    def actors(self) -> tuple[VisibleActor, ...]:
        """Founder-build alias for the shared-kernel visible actor collection."""
        return self.visible_actors

    @property
    def entities(self) -> tuple[VisibleEntity, ...]:
        """Founder-build alias for the shared-kernel visible entity collection."""
        return self.visible_entities


@dataclass(frozen=True, slots=True)
class ActionResult:
    success: bool
    code: str
    summary: str
    event_id: int | None = None
    replayed: bool = False
    data: dict[str, Any] = field(default_factory=dict)
