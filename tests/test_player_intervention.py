from __future__ import annotations

from samseberpg.api import ActionRequest
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


def test_action_request_preserves_give_recipient() -> None:
    request = ActionRequest(
        player_id="player_1",
        action_type=ActionType.GIVE,
        target_id="driftwood_1",
        recipient_id="npc_mira",
    )

    assert request.recipient_id == "npc_mira"
