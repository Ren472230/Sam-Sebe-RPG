from samseberpg.domain import MechanicPrimitive, MechanicSpec
from samseberpg.progression import MechanicValidator


def test_mechanic_validator_accepts_safe_aimed_throw_bonus() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        value=10,
        action="THROW",
        variant="aimed",
    )

    assert validator.validate(spec) == (True, "OK")


def test_mechanic_validator_rejects_out_of_range_accuracy() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        value=100,
        action="THROW",
        variant="aimed",
    )

    assert validator.validate(spec) == (False, "LIMIT_EXCEEDED")


def test_mechanic_validator_rejects_unknown_primitive() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(primitive="CREATE_NUKE", value=1)

    assert validator.validate(spec) == (False, "UNKNOWN_PRIMITIVE")
