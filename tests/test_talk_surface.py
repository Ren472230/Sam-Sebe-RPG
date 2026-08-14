from samseberpg.domain import ActionResult, ActionType, VisibleActor, WorldView
from samseberpg.intent import (
    IntentContext,
    IntentProposal,
    PROPOSAL_ACTION_TYPES,
    canonicalize_proposal,
)
from samseberpg.parser import parse_action
from samseberpg.presentation import HELP_TEXT, render_action_result, render_me


def context():
    return IntentContext(
        "p",
        10,
        "workshop_yard",
        ("village_square",),
        (
            VisibleActor("npc_mira", "Мира", "npc", "работает"),
            VisibleActor("player_other", "Other", "player", None),
        ),
        (),
        (),
    )


def test_exact_talk_forms():
    action = parse_action("говорить npc_mira", "p")
    assert action.action_type == ActionType.TALK
    assert action.target_id == "npc_mira"

    action = parse_action("say npc_mira hello there", "p")
    assert action.action_type == ActionType.TALK
    assert action.target_id == "npc_mira"
    assert action.source_text == "say npc_mira hello there"


def test_semantic_talk_guard_accepts_only_visible_npc():
    assert "TALK" in PROPOSAL_ACTION_TYPES
    good = canonicalize_proposal(
        IntentProposal("TALK", None, "npc_mira", None, "visible NPC"),
        context(),
        source_text="спрошу Миру",
    )
    assert good is not None
    assert good.action_type == ActionType.TALK

    assert canonicalize_proposal(
        IntentProposal("TALK", None, "player_other", None, "player"),
        context(),
        source_text="x",
    ) is None
    assert canonicalize_proposal(
        IntentProposal("TALK", None, "npc_hidden", None, "hidden"),
        context(),
        source_text="x",
    ) is None


def test_presentation_shows_talk_and_progression():
    assert "говорить" in HELP_TEXT or "сказать" in HELP_TEXT
    view = WorldView(
        "p",
        10,
        "workshop_yard",
        "Двор",
        "desc",
        ("village_square",),
        (),
        (),
        (),
        ("THROWING_HABIT_1",),
        ("STEADY_HAND",),
    )
    me_text = render_me(view)
    assert "Рука помнит дугу" in me_text
    assert "Твёрдая рука" in me_text

    result = ActionResult(
        True,
        "OK",
        "done",
        data={
            "unlocks": [
                {
                    "kind": "achievement",
                    "code": "THROWING_HABIT_1",
                    "name": "Рука помнит дугу",
                },
                {
                    "kind": "ability",
                    "code": "STEADY_HAND",
                    "name": "Твёрдая рука",
                },
            ]
        },
    )
    text = render_action_result(result)
    assert "🏆 Открыто достижение: Рука помнит дугу" in text
    assert "✨ Новый навык: Твёрдая рука" in text
