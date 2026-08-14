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


def test_parser_rejects_empty_unknown_and_missing_arguments():
    assert parse_action("", "player_1") is None
    assert parse_action("танцевать на крыше", "player_1") is None
    assert parse_action("идти", "player_1") is None
    assert parse_action("взять", "player_1") is None


def test_parser_supports_explicit_throw_and_give_forms():
    cases = [
        ("бросить stone_flat_1 в tavern_sign", ActionType.THROW, "stone_flat_1", "tavern_sign"),
        ("throw stone_flat_1 at tavern_sign", ActionType.THROW, "stone_flat_1", "tavern_sign"),
        ("дать bread_1 npc_oren", ActionType.GIVE, "bread_1", "npc_oren"),
        ("give bread_1 npc_oren", ActionType.GIVE, "bread_1", "npc_oren"),
    ]
    for text, action_type, item_id, target_id in cases:
        action = parse_action(text, "player_1")
        assert action is not None
        assert action.action_type == action_type
        assert action.item_id == item_id
        assert action.target_id == target_id
        assert action.source_text == text


def test_parser_rejects_malformed_throw_and_give_forms():
    assert parse_action("бросить stone_flat_1", "player_1") is None
    assert parse_action("throw stone_flat_1 tavern_sign", "player_1") is None
    assert parse_action("дать bread_1", "player_1") is None


def test_parser_supports_explicit_buy_and_use_forms():
    cases = [
        ("купить bottle_1 у npc_oren", ActionType.BUY, "bottle_1", "npc_oren"),
        ("buy bottle_1 from npc_oren", ActionType.BUY, "bottle_1", "npc_oren"),
        ("использовать bottle_1 на village_well", ActionType.USE, "bottle_1", "village_well"),
        ("use bottle_1 on village_well", ActionType.USE, "bottle_1", "village_well"),
    ]
    for text, action_type, item_id, target_id in cases:
        action = parse_action(text, "player_1")
        assert action is not None
        assert action.action_type == action_type
        assert action.item_id == item_id
        assert action.target_id == target_id
        assert action.source_text == text


def test_parser_rejects_malformed_buy_and_use_forms():
    assert parse_action("купить bottle_1", "player_1") is None
    assert parse_action("buy bottle_1 npc_oren", "player_1") is None
    assert parse_action("использовать bottle_1", "player_1") is None
    assert parse_action("use bottle_1 village_well", "player_1") is None
