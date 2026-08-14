import pytest

from samseberpg.domain import ActionType, VisibleActor, VisibleEntity, WorldView
from samseberpg.intent import (
    IntentContext,
    IntentProposal,
    IntentResolutionError,
    build_intent_context,
    canonicalize_proposal,
)


def sample_context() -> IntentContext:
    view = WorldView(
        player_id="player_1",
        coins=7,
        location_id="village_square",
        location_name="Деревенская площадь",
        location_description="Площадь",
        exits=("workshop_yard", "river_edge"),
        actors=(
            VisibleActor("npc_oren", "Орен", "npc", "держит таверну открытой"),
            VisibleActor("player_2", "Other", "player"),
        ),
        entities=(
            VisibleEntity("tavern_sign", "Вывеска", "fixture", False, {"condition": 80}),
            VisibleEntity("bottle_offer", "Бутылка", "container", True, {"price": 3}),
            VisibleEntity("village_well", "Колодец", "fixture", False, {"water_source": True}),
        ),
        inventory=(
            VisibleEntity("stone_flat_1", "Плоский камень", "stone", True, {"throwable": True}),
            VisibleEntity("bottle_1", "Бутылка", "container", True, {"fillable": True}),
        ),
    )
    return build_intent_context(view)


@pytest.mark.parametrize(
    ("proposal", "expected_type", "target_id", "item_id", "destination_id"),
    [
        (IntentProposal("LOOK", None, None, None, "look"), ActionType.LOOK, None, None, None),
        (IntentProposal("MOVE", None, None, "river_edge", "move"), ActionType.MOVE, None, None, "river_edge"),
        (IntentProposal("TAKE", None, "bottle_offer", None, "take"), ActionType.TAKE, "bottle_offer", None, None),
        (IntentProposal("DROP", "stone_flat_1", None, None, "drop"), ActionType.DROP, "stone_flat_1", None, None),
        (IntentProposal("THROW", "stone_flat_1", "tavern_sign", None, "throw"), ActionType.THROW, "tavern_sign", "stone_flat_1", None),
        (IntentProposal("GIVE", "stone_flat_1", "npc_oren", None, "give"), ActionType.GIVE, "npc_oren", "stone_flat_1", None),
        (IntentProposal("BUY", "bottle_offer", "npc_oren", None, "buy"), ActionType.BUY, "npc_oren", "bottle_offer", None),
        (IntentProposal("USE", "bottle_1", "village_well", None, "use"), ActionType.USE, "village_well", "bottle_1", None),
    ],
)
def test_canonicalizer_accepts_context_legal_proposals(
    proposal, expected_type, target_id, item_id, destination_id
):
    action = canonicalize_proposal(proposal, sample_context(), source_text="natural text")
    assert action is not None
    assert action.actor_id == "player_1"
    assert action.action_type == expected_type
    assert action.target_id == target_id
    assert action.item_id == item_id
    assert action.destination_id == destination_id
    assert action.source_text == "natural text"


@pytest.mark.parametrize(
    "proposal",
    [
        IntentProposal("UNSUPPORTED", None, None, None, "unsupported"),
        IntentProposal("MOVE", None, None, "secret_castle", "hallucinated exit"),
        IntentProposal("TAKE", None, "stone_flat_1", None, "inventory is not visible ground"),
        IntentProposal("DROP", "tavern_sign", None, None, "not inventory"),
        IntentProposal("THROW", "missing_item", "tavern_sign", None, "bad item"),
        IntentProposal("THROW", "stone_flat_1", "hidden_target", None, "bad target"),
        IntentProposal("GIVE", "stone_flat_1", "npc_hidden", None, "bad actor"),
        IntentProposal("BUY", "stone_flat_1", "npc_oren", None, "inventory cannot be bought"),
        IntentProposal("USE", "bottle_1", "hidden_well", None, "bad target"),
        IntentProposal("LOOK", "stone_flat_1", None, None, "extraneous field"),
    ],
)
def test_canonicalizer_rejects_unsupported_hallucinated_or_illegal_references(proposal):
    assert canonicalize_proposal(proposal, sample_context(), source_text="x") is None


def test_intent_context_is_built_only_from_world_view():
    context = sample_context()
    assert context.player_id == "player_1"
    assert context.coins == 7
    assert context.exits == ("workshop_yard", "river_edge")
    assert context.visible_actor_ids == frozenset({"npc_oren", "player_2"})
    assert context.visible_entity_ids == frozenset({"tavern_sign", "bottle_offer", "village_well"})
    assert context.inventory_ids == frozenset({"stone_flat_1", "bottle_1"})


def test_proposal_payload_validation_is_strict():
    proposal = IntentProposal.from_payload(
        {
            "action_type": "TAKE",
            "item_id": None,
            "target_id": "bottle_offer",
            "destination_id": None,
            "reason": "player asked to pick it up",
        }
    )
    assert proposal.action_type == "TAKE"

    with pytest.raises(IntentResolutionError):
        IntentProposal.from_payload({"action_type": "DELETE_WORLD"})
    with pytest.raises(IntentResolutionError):
        IntentProposal.from_payload(
            {
                "action_type": "LOOK",
                "item_id": 42,
                "target_id": None,
                "destination_id": None,
                "reason": "bad type",
            }
        )
