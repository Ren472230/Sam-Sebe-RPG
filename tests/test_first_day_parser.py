from samseberpg.domain import ActionType
from samseberpg.parser import parse_command


def test_parse_talk_command() -> None:
    action = parse_command("поговорить mira_craftswoman")
    assert action is not None
    assert action.action_type == ActionType.TALK
    assert action.target_id == "mira_craftswoman"


def test_parse_lodging_topic() -> None:
    action = parse_command("спросить oren_innkeeper о ночлеге")
    assert action is not None
    assert action.action_type == ActionType.TALK
    assert action.target_id == "oren_innkeeper"
    assert action.modifiers["topic"] == "lodging"


def test_parse_give_command() -> None:
    action = parse_command("дать stone_flat_1 mira_craftswoman")
    assert action is not None
    assert action.action_type == ActionType.GIVE
    assert action.item_id == "stone_flat_1"
    assert action.target_id == "mira_craftswoman"


def test_parse_feed_command() -> None:
    action = parse_command("покормить raven_1 bread_1")
    assert action is not None
    assert action.action_type == ActionType.FEED
    assert action.target_id == "raven_1"
    assert action.item_id == "bread_1"


def test_parse_explicit_lodging_payment() -> None:
    action = parse_command("оплатить ночлег")
    assert action is not None
    assert action.action_type == ActionType.TALK
    assert action.target_id == "oren_innkeeper"
    assert action.modifiers["topic"] == "pay_lodging"


def test_parse_explicit_social_lodging_request() -> None:
    action = parse_command("попросить ночлег")
    assert action is not None
    assert action.action_type == ActionType.TALK
    assert action.target_id == "oren_innkeeper"
    assert action.modifiers["topic"] == "request_lodging"
