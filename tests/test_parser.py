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
