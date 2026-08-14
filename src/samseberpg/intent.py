from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .domain import ActionType, CanonicalAction, VisibleActor, VisibleEntity, WorldView


PROPOSAL_ACTION_TYPES = frozenset({
    "LOOK",
    "MOVE",
    "TAKE",
    "DROP",
    "THROW",
    "GIVE",
    "BUY",
    "USE",
    "UNSUPPORTED",
})


class IntentResolutionError(RuntimeError):
    """Expected failure while obtaining or validating an intent proposal."""


@dataclass(frozen=True, slots=True)
class IntentContext:
    player_id: str
    coins: int
    location_id: str
    exits: tuple[str, ...]
    actors: tuple[VisibleActor, ...]
    entities: tuple[VisibleEntity, ...]
    inventory: tuple[VisibleEntity, ...]

    @property
    def visible_actor_ids(self) -> frozenset[str]:
        return frozenset(actor.id for actor in self.actors)

    @property
    def visible_entity_ids(self) -> frozenset[str]:
        return frozenset(entity.id for entity in self.entities)

    @property
    def inventory_ids(self) -> frozenset[str]:
        return frozenset(entity.id for entity in self.inventory)

    def to_payload(self) -> dict[str, Any]:
        def actor_payload(actor: VisibleActor) -> dict[str, Any]:
            return {
                "id": actor.id,
                "name": actor.name,
                "actor_type": actor.actor_type,
                "activity": actor.activity,
            }

        def entity_payload(entity: VisibleEntity) -> dict[str, Any]:
            return {
                "id": entity.id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "portable": entity.portable,
                "state": entity.state,
            }

        return {
            "player_id": self.player_id,
            "coins": self.coins,
            "location_id": self.location_id,
            "exits": list(self.exits),
            "visible_actors": [actor_payload(actor) for actor in self.actors],
            "visible_entities": [entity_payload(entity) for entity in self.entities],
            "inventory": [entity_payload(entity) for entity in self.inventory],
        }


@dataclass(frozen=True, slots=True)
class IntentProposal:
    action_type: str
    item_id: str | None
    target_id: str | None
    destination_id: str | None
    reason: str

    @classmethod
    def from_payload(cls, payload: Any) -> "IntentProposal":
        required = {"action_type", "item_id", "target_id", "destination_id", "reason"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise IntentResolutionError("intent proposal must contain exactly the expected fields")
        action_type = payload["action_type"]
        if not isinstance(action_type, str) or action_type not in PROPOSAL_ACTION_TYPES:
            raise IntentResolutionError("unsupported intent proposal action_type")
        for key in ("item_id", "target_id", "destination_id"):
            value = payload[key]
            if value is not None and not isinstance(value, str):
                raise IntentResolutionError(f"{key} must be a string or null")
        reason = payload["reason"]
        if not isinstance(reason, str):
            raise IntentResolutionError("reason must be a string")
        return cls(
            action_type=action_type,
            item_id=payload["item_id"],
            target_id=payload["target_id"],
            destination_id=payload["destination_id"],
            reason=reason,
        )


class IntentResolver(Protocol):
    def resolve(self, text: str, context: IntentContext) -> IntentProposal: ...


def build_intent_context(view: WorldView) -> IntentContext:
    return IntentContext(
        player_id=view.player_id,
        coins=view.coins,
        location_id=view.location_id,
        exits=view.exits,
        actors=view.actors,
        entities=view.entities,
        inventory=view.inventory,
    )


def canonicalize_proposal(
    proposal: IntentProposal,
    context: IntentContext,
    *,
    source_text: str,
) -> CanonicalAction | None:
    action_type = proposal.action_type
    item_id = proposal.item_id
    target_id = proposal.target_id
    destination_id = proposal.destination_id

    if action_type == "UNSUPPORTED":
        return None

    if action_type == "LOOK":
        if any(value is not None for value in (item_id, target_id, destination_id)):
            return None
        return CanonicalAction(context.player_id, ActionType.LOOK, source_text=source_text)

    if action_type == "MOVE":
        if item_id is not None or target_id is not None or destination_id not in context.exits:
            return None
        return CanonicalAction(
            context.player_id,
            ActionType.MOVE,
            destination_id=destination_id,
            source_text=source_text,
        )

    if action_type == "TAKE":
        if item_id is not None or destination_id is not None or target_id not in context.visible_entity_ids:
            return None
        return CanonicalAction(
            context.player_id,
            ActionType.TAKE,
            target_id=target_id,
            source_text=source_text,
        )

    if action_type == "DROP":
        if target_id is not None or destination_id is not None or item_id not in context.inventory_ids:
            return None
        return CanonicalAction(
            context.player_id,
            ActionType.DROP,
            target_id=item_id,
            source_text=source_text,
        )

    if action_type in {"THROW", "USE"}:
        if destination_id is not None or item_id not in context.inventory_ids or target_id not in context.visible_entity_ids:
            return None
        canonical_type = ActionType.THROW if action_type == "THROW" else ActionType.USE
        return CanonicalAction(
            context.player_id,
            canonical_type,
            item_id=item_id,
            target_id=target_id,
            source_text=source_text,
        )

    if action_type == "GIVE":
        if destination_id is not None or item_id not in context.inventory_ids or target_id not in context.visible_actor_ids:
            return None
        return CanonicalAction(
            context.player_id,
            ActionType.GIVE,
            item_id=item_id,
            target_id=target_id,
            source_text=source_text,
        )

    if action_type == "BUY":
        if destination_id is not None or item_id not in context.visible_entity_ids or target_id not in context.visible_actor_ids:
            return None
        return CanonicalAction(
            context.player_id,
            ActionType.BUY,
            item_id=item_id,
            target_id=target_id,
            source_text=source_text,
        )

    return None
