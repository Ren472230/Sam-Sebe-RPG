from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from samseberpg.domain import ActionType


def parser():
    try:
        from samseberpg.parser import parse_command
    except ImportError as exc:
        pytest.fail(f"Parser is not implemented yet: {exc}")
    return parse_command


def test_parse_russian_look() -> None:
    action = parser()("осмотреться")
    assert action is not None
    assert action.action_type is ActionType.LOOK


def test_parse_move_destination() -> None:
    action = parser()("идти workshop_yard")
    assert action is not None
    assert action.action_type is ActionType.MOVE
    assert action.destination_id == "workshop_yard"


def test_parse_take_item() -> None:
    action = parser()("взять stone_flat_1")
    assert action is not None
    assert action.action_type is ActionType.TAKE
    assert action.item_id == "stone_flat_1"


def test_parse_throw_item_at_target() -> None:
    action = parser()("бросить stone_flat_1 в target_barrel")
    assert action is not None
    assert action.action_type is ActionType.THROW
    assert action.item_id == "stone_flat_1"
    assert action.target_id == "target_barrel"
    assert action.modifiers.get("aimed") is not True


def test_parse_aimed_throw_sets_modifier() -> None:
    action = parser()("прицельно бросить stone_flat_1 в target_barrel")
    assert action is not None
    assert action.action_type is ActionType.THROW
    assert action.modifiers["aimed"] is True


def test_unknown_input_returns_none() -> None:
    assert parser()("спеть балладу луне") is None


def test_parse_drop_item() -> None:
    action = parser()("оставить stone_flat_1")
    assert action is not None
    assert action.action_type is ActionType.DROP
    assert action.item_id == "stone_flat_1"


def test_parse_wait_ticks() -> None:
    action = parser()("ждать 3")
    assert action is not None
    assert action.action_type is ActionType.WAIT
    assert action.modifiers["ticks"] == 3
