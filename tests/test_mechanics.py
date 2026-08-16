from __future__ import annotations

from samseberpg.domain import MechanicPrimitive, MechanicSpec
from samseberpg.progression import AIMED_THROW_SPEC, MechanicValidator


def test_valid_aimed_throw_accuracy_bonus_is_accepted() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(
        mechanic_id="aimed_throw",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude=0.10,
    )

    assert validator.validate(spec) == (True, "OK")
    assert validator.validate(AIMED_THROW_SPEC) == (True, "OK")


def test_out_of_range_accuracy_bonus_is_rejected() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(
        mechanic_id="god_throw",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude=1.00,
    )

    assert validator.validate(spec) == (False, "LIMIT_EXCEEDED")


def test_unknown_primitive_is_rejected_without_dynamic_execution() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(
        mechanic_id="unsafe",
        primitive="EXECUTE_CODE",
        magnitude=0.01,
    )

    assert validator.validate(spec) == (False, "UNKNOWN_PRIMITIVE")


def test_numeric_modifier_requires_a_non_negative_number() -> None:
    validator = MechanicValidator()

    invalid_type = MechanicSpec(
        mechanic_id="bad_type",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude="ten percent",
    )
    negative = MechanicSpec(
        mechanic_id="negative",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude=-0.10,
    )

    assert validator.validate(invalid_type) == (False, "INVALID_MAGNITUDE")
    assert validator.validate(negative) == (False, "INVALID_MAGNITUDE")
