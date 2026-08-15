from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .domain import ActionType, CanonicalAction, WorldView


_ALLOWED_ACTIONS = frozenset(action.value for action in ActionType)
_PROPOSAL_FIELDS = frozenset({"action_type", "item_id", "target_id", "destination_id", "reason"})


class IntentResolutionError(ValueError):
    """Raised when an untrusted intent payload violates the closed proposal schema."""


@dataclass(frozen=True, slots=True)
class IntentProposal:
    action_type: str
    item_id: str | None
    target_id: str | None
    destination_id: str | None
    reason: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "IntentProposal":
        if not isinstance(payload, Mapping):
            raise IntentResolutionError("Intent payload must be an object")
        if frozenset(payload.keys()) != _PROPOSAL_FIELDS:
            raise IntentResolutionError("Intent payload fields do not match the closed schema")

        action_type = payload["action_type"]
        if not isinstance(action_type, str) or action_type not in _ALLOWED_ACTIONS:
            raise IntentResolutionError("Unsupported action_type")

        values: dict[str, str | None] = {}
        for key in ("item_id", "target_id", "destination_id"):
            value = payload[key]
            if value is not None and not isinstance(value, str):
                raise IntentResolutionError(f"{key} must be a string or null")
            values[key] = value

        reason = payload["reason"]
        if not isinstance(reason, str):
            raise IntentResolutionError("reason must be a string")

        return cls(
            action_type=action_type,
            item_id=values["item_id"],
            target_id=values["target_id"],
            destination_id=values["destination_id"],
            reason=reason,
        )


@dataclass(frozen=True, slots=True)
class IntentContext:
    player_id: str
    coins: int
    location_id: str
    location_name: str
    exits: tuple[str, ...]
    visible_actors: tuple[dict[str, Any], ...]
    visible_entities: tuple[dict[str, Any], ...]
    inventory: tuple[dict[str, Any], ...]

    @property
    def visible_actor_ids(self) -> frozenset[str]:
        return frozenset(str(actor["id"]) for actor in self.visible_actors)

    @property
    def visible_npc_ids(self) -> frozenset[str]:
        return frozenset(
            str(actor["id"])
            for actor in self.visible_actors
            if actor.get("actor_type") == "npc"
        )

    @property
    def visible_entity_ids(self) -> frozenset[str]:
        return frozenset(str(entity["id"]) for entity in self.visible_entities)

    @property
    def inventory_ids(self) -> frozenset[str]:
        return frozenset(str(entity["id"]) for entity in self.inventory)

    def to_payload(self) -> dict[str, Any]:
        """Return only evidence visible to this player; no hidden world state leaks out."""
        return {
            "player_id": self.player_id,
            "coins": self.coins,
            "location_id": self.location_id,
            "location_name": self.location_name,
            "exits": list(self.exits),
            "visible_actors": [dict(item) for item in self.visible_actors],
            "visible_entities": [dict(item) for item in self.visible_entities],
            "inventory": [dict(item) for item in self.inventory],
        }


def build_intent_context(view: WorldView) -> IntentContext:
    """Project authoritative WorldView into the only facts an intent resolver may use."""
    return IntentContext(
        player_id=view.player_id,
        coins=view.coins,
        location_id=view.location_id,
        location_name=view.location_name,
        exits=tuple(view.exits),
        visible_actors=tuple(
            {
                "id": actor.actor_id,
                "name": actor.name,
                "actor_type": actor.actor_type,
                "activity": actor.activity,
            }
            for actor in view.visible_actors
        ),
        visible_entities=tuple(
            {
                "id": entity.entity_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "portable": entity.portable,
                "state": dict(entity.state),
            }
            for entity in view.visible_entities
        ),
        inventory=tuple(
            {
                "id": entity.entity_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "portable": entity.portable,
                "state": dict(entity.state),
            }
            for entity in view.inventory
        ),
    )


def canonicalize_proposal(
    proposal: IntentProposal,
    context: IntentContext,
    *,
    source_text: str,
) -> CanonicalAction | None:
    """Convert an untrusted proposal only when every reference is world-grounded.

    Returning ``None`` is intentional: an LLM or future resolver may propose a plausible
    but nonexistent target. The simulation must never execute such a guess.
    """
    try:
        action_type = ActionType(proposal.action_type)
    except ValueError:
        return None

    item_id = proposal.item_id
    target_id = proposal.target_id
    destination_id = proposal.destination_id
    inventory_ids = context.inventory_ids
    visible_entity_ids = context.visible_entity_ids
    visible_actor_ids = context.visible_actor_ids
    visible_npc_ids = context.visible_npc_ids

    if action_type is ActionType.LOOK:
        if any((item_id, target_id, destination_id)):
            return None
    elif action_type is ActionType.MOVE:
        if item_id is not None or target_id is not None:
            return None
        if destination_id not in context.exits:
            return None
    elif action_type is ActionType.TAKE:
        if item_id is not None or destination_id is not None:
            return None
        if target_id not in visible_entity_ids:
            return None
    elif action_type is ActionType.DROP:
        if target_id is not None or destination_id is not None:
            return None
        if item_id not in inventory_ids:
            return None
        target_id = item_id
        item_id = None
    elif action_type is ActionType.THROW:
        if destination_id is not None:
            return None
        if item_id not in inventory_ids:
            return None
        if target_id not in visible_entity_ids and target_id not in visible_actor_ids:
            return None
    elif action_type is ActionType.GIVE:
        if destination_id is not None:
            return None
        if item_id not in inventory_ids or target_id not in visible_actor_ids:
            return None
    elif action_type is ActionType.BUY:
        if destination_id is not None:
            return None
        if item_id not in visible_entity_ids or target_id not in visible_actor_ids:
            return None
    elif action_type is ActionType.USE:
        if destination_id is not None:
            return None
        if item_id not in inventory_ids or target_id not in visible_entity_ids:
            return None
    elif action_type is ActionType.TALK:
        if item_id is not None or destination_id is not None:
            return None
        if target_id not in visible_npc_ids:
            return None
    else:
        return None

    return CanonicalAction(
        actor_id=context.player_id,
        action_type=action_type,
        target_id=target_id,
        destination_id=destination_id,
        source_text=source_text,
        item_id=item_id,
    )
