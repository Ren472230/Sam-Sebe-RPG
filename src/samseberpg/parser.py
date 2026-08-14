from __future__ import annotations

from .domain import ActionType, CanonicalAction


_LOOK_WORDS = {"осмотреться", "осмотреть", "look"}
_MOVE_WORDS = {"идти", "пойти", "move"}
_TAKE_WORDS = {"взять", "поднять", "take"}
_DROP_WORDS = {"положить", "drop"}
_THROW_WORDS = {"бросить", "throw"}
_GIVE_WORDS = {"дать", "give"}
_BUY_WORDS = {"купить", "buy"}
_USE_WORDS = {"использовать", "use"}
_THROW_CONNECTORS = {"в", "at"}
_BUY_CONNECTORS = {"у", "from"}
_USE_CONNECTORS = {"на", "on"}


def parse_action(text: str, player_id: str) -> CanonicalAction | None:
    source = text.strip()
    if not source:
        return None

    parts = source.split()
    verb = parts[0].casefold()

    if verb in _LOOK_WORDS and len(parts) == 1:
        return CanonicalAction(player_id, ActionType.LOOK, source_text=source)
    if verb in _MOVE_WORDS and len(parts) == 2:
        return CanonicalAction(
            player_id,
            ActionType.MOVE,
            destination_id=parts[1],
            source_text=source,
        )
    if verb in _TAKE_WORDS and len(parts) == 2:
        return CanonicalAction(
            player_id,
            ActionType.TAKE,
            target_id=parts[1],
            source_text=source,
        )
    if verb in _DROP_WORDS and len(parts) == 2:
        return CanonicalAction(
            player_id,
            ActionType.DROP,
            target_id=parts[1],
            source_text=source,
        )
    if (
        verb in _THROW_WORDS
        and len(parts) == 4
        and parts[2].casefold() in _THROW_CONNECTORS
    ):
        return CanonicalAction(
            player_id,
            ActionType.THROW,
            item_id=parts[1],
            target_id=parts[3],
            source_text=source,
        )
    if verb in _GIVE_WORDS and len(parts) == 3:
        return CanonicalAction(
            player_id,
            ActionType.GIVE,
            item_id=parts[1],
            target_id=parts[2],
            source_text=source,
        )
    if (
        verb in _BUY_WORDS
        and len(parts) == 4
        and parts[2].casefold() in _BUY_CONNECTORS
    ):
        return CanonicalAction(
            player_id,
            ActionType.BUY,
            item_id=parts[1],
            target_id=parts[3],
            source_text=source,
        )
    if (
        verb in _USE_WORDS
        and len(parts) == 4
        and parts[2].casefold() in _USE_CONNECTORS
    ):
        return CanonicalAction(
            player_id,
            ActionType.USE,
            item_id=parts[1],
            target_id=parts[3],
            source_text=source,
        )
    return None
