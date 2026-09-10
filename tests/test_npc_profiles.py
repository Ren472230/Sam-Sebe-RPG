from __future__ import annotations

import pytest

from samseberpg.npc_profiles import get_npc_profile


def test_profiles_cover_three_living_npcs() -> None:
    assert get_npc_profile("npc_oren").display_name == "Орен"
    assert get_npc_profile("npc_mira").display_name == "Мира"
    assert get_npc_profile("npc_kaspar").display_name == "Каспар"
    assert get_npc_profile("npc_mira").personality != get_npc_profile("npc_kaspar").personality


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(LookupError):
        get_npc_profile("npc_missing")
