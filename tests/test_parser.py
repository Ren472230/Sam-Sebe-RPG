from samseberpg.domain import ActionType
from samseberpg.parser import parse_command


def test_parse_look_russian() -> None:
    action = parse_command("осмотреться")
    assert action is not None
    assert action.action_type == ActionType.LOOK


def test_parse_move_take_drop_and_wait() -> None:
    move = parse_command("идти village_square")
    take = parse_command("взять stone_flat_1")
    drop = parse_command("бросить_на_землю stone_flat_1")
    wait = parse_command("ждать 3")

    assert move.destination_id == "village_square"
    assert take.item_id == "stone_flat_1"
    assert drop.item_id == "stone_flat_1"
    assert wait.modifiers == {"ticks": 3}


def test_parse_throw_and_aimed_throw() -> None:
    normal = parse_command("бросить stone_flat_1 в target_barrel")
    aimed = parse_command("прицельно бросить stone_round_1 в target_sign")

    assert normal.action_type == ActionType.THROW
    assert normal.item_id == "stone_flat_1"
    assert normal.target_id == "target_barrel"
    assert normal.modifiers == {}

    assert aimed.action_type == ActionType.THROW
    assert aimed.item_id == "stone_round_1"
    assert aimed.target_id == "target_sign"
    assert aimed.modifiers == {"aimed": True}


def test_unknown_command_returns_none() -> None:
    assert parse_command("преврати мир в сыр") is None
