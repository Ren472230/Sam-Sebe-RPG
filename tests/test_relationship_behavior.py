from __future__ import annotations

from samseberpg.conversation_state import relationship_behavior


def _relation(**overrides: int) -> dict[str, int]:
    relation = {
        "familiarity": 0,
        "trust": 0,
        "affinity": 0,
        "fear": 0,
        "conflict": 0,
        "romance": 0,
    }
    relation.update(overrides)
    return relation


def test_new_stranger_is_guarded() -> None:
    assert relationship_behavior(_relation()) == "guarded"


def test_positive_familiar_relation_becomes_comfortable() -> None:
    assert relationship_behavior(_relation(familiarity=20, trust=15, affinity=10)) == "comfortable"


def test_high_trust_and_affinity_becomes_warm() -> None:
    assert relationship_behavior(_relation(familiarity=30, trust=35, affinity=30)) == "warm"


def test_conflict_or_fear_outweighs_mild_positive_relation() -> None:
    assert relationship_behavior(_relation(familiarity=20, trust=10, conflict=30)) == "distrustful"
    assert relationship_behavior(_relation(familiarity=20, affinity=10, fear=30)) == "distrustful"


def test_severe_conflict_is_hostile() -> None:
    assert relationship_behavior(_relation(trust=-20, affinity=-10, conflict=60)) == "hostile"


def test_small_known_relation_is_neutral() -> None:
    assert relationship_behavior(_relation(familiarity=5, trust=2, affinity=1)) == "neutral"
