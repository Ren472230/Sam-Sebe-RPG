from __future__ import annotations

from samseberpg.domain import ActionType, CanonicalAction


def test_give_action_contract_exposes_recipient() -> None:
    action = CanonicalAction(
        actor_id="player_1",
        action_type=ActionType.GIVE,
        target_id="driftwood_1",
        recipient_id="npc_mira",
    )

    assert action.action_type.value == "GIVE"
    assert action.target_id == "driftwood_1"
    assert action.recipient_id == "npc_mira"
