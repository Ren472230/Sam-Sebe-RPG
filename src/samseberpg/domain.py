from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    LOOK = "LOOK"
    MOVE = "MOVE"
    TAKE = "TAKE"
    DROP = "DROP"
    GIVE = "GIVE"
    USE = "USE"
    THROW = "THROW"
    FEED = "FEED"
    WAIT = "WAIT"


@dataclass(frozen=True, slots=True)
class CanonicalAction:
    actor_id: str
    action_type: ActionType
    target_id: str | None = None
    item_id: str | None = None
    destination_id: str | None = None
    modifiers: dict[str, Any] = field(default_factory=dict)
    source_text: str | None = None


@dataclass(frozen=True, slots=True)
class ActionResult:
    success: bool
    code: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActionEvent:
    event_id: int | None
    world_time: int
    actor_id: str
    action_type: ActionType
    target_id: str | None
    item_id: str | None
    location_id: str | None
    success: bool
    result_code: str
    behavior_tags: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


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
    primitive: MechanicPrimitive | str
    magnitude: float | None = None
    action_family: str | None = None
    variant: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        primitive = self.primitive.value if isinstance(self.primitive, MechanicPrimitive) else self.primitive
        return {
            "primitive": primitive,
            "magnitude": self.magnitude,
            "action_family": self.action_family,
            "variant": self.variant,
            "metadata": self.metadata,
        }
