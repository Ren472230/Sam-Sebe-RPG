from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
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


class MechanicPrimitive(StrEnum):
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
    value: float | int | str
    action: str | None = None
    variant: str | None = None
    condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        primitive = self.primitive.value if isinstance(self.primitive, MechanicPrimitive) else self.primitive
        data: dict[str, Any] = {"primitive": primitive, "value": self.value}
        if self.action is not None:
            data["action"] = self.action
        if self.variant is not None:
            data["variant"] = self.variant
        if self.condition is not None:
            data["condition"] = self.condition
        return data
