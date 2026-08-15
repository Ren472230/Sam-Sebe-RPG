from samseberpg.domain import (
    ActionResult,
    ActionType,
    CanonicalAction,
    VisibleActor,
    VisibleEntity,
    WorldView,
)


def test_founder_actions_extend_the_shared_kernel_without_replacing_it():
    assert {ActionType.LOOK, ActionType.MOVE, ActionType.TAKE, ActionType.DROP} <= set(ActionType)
    assert {ActionType.THROW, ActionType.GIVE, ActionType.BUY, ActionType.USE, ActionType.TALK} <= set(ActionType)


def test_canonical_action_can_carry_a_distinct_item_id():
    action = CanonicalAction(
        actor_id="player_1",
        action_type=ActionType.THROW,
        item_id="stone_1",
        target_id="tavern_sign",
    )
    assert action.item_id == "stone_1"
    assert action.target_id == "tavern_sign"


def test_action_result_can_carry_structured_evidence_without_breaking_old_callers():
    plain = ActionResult(True, "OK", "done")
    rich = ActionResult(True, "OK", "done", data={"damage": 20})
    assert plain.data == {}
    assert rich.data == {"damage": 20}


def test_visible_models_keep_shared_kernel_names_and_offer_founder_aliases():
    actor = VisibleActor(actor_id="npc_mira", name="Mira", actor_type="npc", activity="sweeping")
    entity = VisibleEntity(
        entity_id="stone_1",
        name="Stone",
        entity_type="item",
        portable=True,
        state={"throwable": True},
    )
    assert actor.actor_id == actor.id == "npc_mira"
    assert actor.activity == "sweeping"
    assert entity.entity_id == entity.id == "stone_1"
    assert entity.state == {"throwable": True}


def test_world_view_is_additive_and_exposes_founder_collection_aliases():
    actor = VisibleActor(actor_id="npc_mira", name="Mira", actor_type="npc")
    entity = VisibleEntity(entity_id="stone_1", name="Stone", entity_type="item", portable=True)
    view = WorldView(
        player_id="player_1",
        location_id="workshop_yard",
        location_name="Workshop Yard",
        location_description="A yard.",
        visible_actors=(actor,),
        visible_entities=(entity,),
        inventory=(),
        coins=10,
        exits=("village_square",),
        achievement_codes=("THROWING_HABIT_1",),
        ability_codes=("STEADY_HAND",),
    )
    assert view.actors == view.visible_actors == (actor,)
    assert view.entities == view.visible_entities == (entity,)
    assert view.coins == 10
    assert view.exits == ("village_square",)
