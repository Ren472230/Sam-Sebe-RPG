from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def mechanic_types():
    try:
        from samseberpg.domain import MechanicPrimitive, MechanicSpec
        from samseberpg.progression import MechanicValidator
    except ImportError as exc:
        pytest.fail(f"Mechanic validator boundary is not implemented yet: {exc}")
    return MechanicPrimitive, MechanicSpec, MechanicValidator


def test_validator_accepts_aimed_throw_accuracy_bonus() -> None:
    primitive, spec_type, validator_type = mechanic_types()
    spec = spec_type(
        primitive=primitive.MODIFY_ACCURACY,
        magnitude=10,
        action_family="THROW",
        metadata={"when": {"modifier": "aimed"}},
    )

    valid, reason = validator_type().validate(spec)

    assert valid is True
    assert reason == "OK"


def test_validator_rejects_accuracy_bonus_above_limit() -> None:
    primitive, spec_type, validator_type = mechanic_types()
    spec = spec_type(
        primitive=primitive.MODIFY_ACCURACY,
        magnitude=100,
        action_family="THROW",
    )

    valid, reason = validator_type().validate(spec)

    assert valid is False
    assert reason == "ACCURACY_LIMIT_EXCEEDED"


def test_validator_rejects_unknown_primitive() -> None:
    _primitive, spec_type, validator_type = mechanic_types()
    spec = spec_type(primitive="EXECUTE_PYTHON", magnitude=1, action_family="THROW")

    valid, reason = validator_type().validate(spec)

    assert valid is False
    assert reason == "UNKNOWN_PRIMITIVE"
