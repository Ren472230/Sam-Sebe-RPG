from samseberpg.domain import ActionType
from samseberpg.parser import parse_action


def test_parser_supports_russian_and_english_core_actions():
    cases = [
        ("осмотреться", ActionType.LOOK, None, None),
        ("look", ActionType.LOOK, None, None),
        ("идти village_square", ActionType.MOVE, None, "village_square"),
        ("move river_edge", ActionType.MOVE, None, "river_edge"),
        ("взять stone_flat_1", ActionType.TAKE, "stone_flat_1", None),
        ("take apple_1", ActionType.TAKE, "apple_1", None),
        ("положить stone_flat_1", ActionType.DROP, "stone_flat_1", None),
        ("drop rope_1", ActionType.DROP, "rope_1", None),
    ]
    for text, action_type, target_id, destination_id in cases:
        action = parse_action(text, "player_1")
        assert action is not None
        assert action.actor_id == "player_1"
        assert action.action_type == action_type
        assert action.target_id == target_id
        assert action.destination_id == destination_id
        assert action.source_text == text


def test_parser_supports_throw_give_buy_use_and_talk():
    cases = [
        ("бросить stone_flat_1 в tavern_sign", ActionType.THROW, "stone_flat_1", "tavern_sign"),
        ("throw stone_flat_1 at tavern_sign", ActionType.THROW, "stone_flat_1", "tavern_sign"),
        ("дать bread_1 npc_oren", ActionType.GIVE, "bread_1", "npc_oren"),
        ("give bread_1 npc_oren", ActionType.GIVE, "bread_1", "npc_oren"),
        ("купить bottle_1 у npc_oren", ActionType.BUY, "bottle_1", "npc_oren"),
        ("buy bottle_1 from npc_oren", ActionType.BUY, "bottle_1", "npc_oren"),
        ("использовать bottle_1 на village_well", ActionType.USE, "bottle_1", "village_well"),
        ("use bottle_1 on village_well", ActionType.USE, "bottle_1", "village_well"),
        ("говорить npc_mira", ActionType.TALK, None, "npc_mira"),
        ("talk npc_mira", ActionType.TALK, None, "npc_mira"),
    ]
    for text, action_type, item_id, target_id in cases:
        action = parse_action(text, "player_1")
        assert action is not None
        assert action.action_type == action_type
        assert action.item_id == item_id
        assert action.target_id == target_id
        assert action.source_text == text


def test_say_preserves_full_utterance_for_authoritative_talk_layer():
    text = "сказать npc_mira привет, как дела?"
    action = parse_action(text, "player_1")
    assert action is not None
    assert action.action_type == ActionType.TALK
    assert action.target_id == "npc_mira"
    assert action.source_text == text


def test_parser_is_whitespace_tolerant_but_preserves_trimmed_source_text():
    action = parse_action("   взять stone_flat_1   ", "player_1")
    assert action is not None
    assert action.target_id == "stone_flat_1"
    assert action.source_text == "взять stone_flat_1"


def test_parser_rejects_empty_unknown_or_malformed_commands():
    malformed = [
        "",
        "танцевать на крыше",
        "идти",
        "взять",
        "бросить stone_flat_1",
        "throw stone_flat_1 tavern_sign",
        "дать bread_1",
        "купить bottle_1",
        "buy bottle_1 npc_oren",
        "использовать bottle_1",
        "use bottle_1 village_well",
        "говорить",
        "сказать npc_mira",
    ]
    assert all(parse_action(text, "player_1") is None for text in malformed)
