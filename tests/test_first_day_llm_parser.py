import json
from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType
from samseberpg.llm_parser import ACTION_SCHEMA, OllamaActionParser, build_parser_context


def make_db(tmp_path: Path) -> GameDatabase:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize(); db.bootstrap_if_empty()
    return db


def response_for(data: dict):
    def transport(url, payload, timeout):
        return {"message": {"content": json.dumps(data)}}
    return transport


def test_schema_supports_first_day_actions_and_topic() -> None:
    actions = set(ACTION_SCHEMA["properties"]["action_type"]["enum"])
    assert {"TALK", "GIVE", "FEED"}.issubset(actions)
    assert "topic" in ACTION_SCHEMA["properties"]


def test_llm_parser_maps_lodging_talk_with_visible_npc(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE player_state SET location_id='village_square' WHERE player_id='player_1'")
    context = build_parser_context(db)
    parser = OllamaActionParser(
        model="fake",
        transport=response_for({
            "recognized": True,
            "action_type": "TALK",
            "target_id": "oren_innkeeper",
            "item_id": None,
            "destination_id": None,
            "aimed": False,
            "ticks": 1,
            "topic": "lodging",
        }),
    )
    action = parser.parse("спрошу у трактирщика, где переночевать", context)
    assert action is not None
    assert action.action_type == ActionType.TALK
    assert action.target_id == "oren_innkeeper"
    assert action.modifiers["topic"] == "lodging"


def test_llm_parser_rejects_entity_id_not_in_context(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    context = build_parser_context(db)
    parser = OllamaActionParser(
        model="fake",
        transport=response_for({
            "recognized": True,
            "action_type": "TALK",
            "target_id": "invented_wizard",
            "item_id": None,
            "destination_id": None,
            "aimed": False,
            "ticks": 1,
            "topic": None,
        }),
    )
    assert parser.parse("поговорю с волшебником", context) is None


def test_schema_constrains_lodging_topics_to_canonical_values() -> None:
    topic_schema = ACTION_SCHEMA["properties"]["topic"]
    assert set(topic_schema["enum"]) == {
        None,
        "lodging",
        "pay_lodging",
        "request_lodging",
    }


def test_llm_parser_rejects_unknown_talk_topic(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE player_state SET location_id='village_square' WHERE player_id='player_1'")
    context = build_parser_context(db)
    parser = OllamaActionParser(
        model="fake",
        transport=response_for({
            "recognized": True,
            "action_type": "TALK",
            "target_id": "oren_innkeeper",
            "item_id": None,
            "destination_id": None,
            "aimed": False,
            "ticks": 1,
            "topic": "invent_a_quest",
        }),
    )
    assert parser.parse("попросить странный квест", context) is None
