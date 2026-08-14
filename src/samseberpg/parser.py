from __future__ import annotations

from .domain import ActionType, CanonicalAction


_LOOK_WORDS = {"осмотреться", "осмотреть", "look"}
_MOVE_WORDS = {"идти", "пойти", "move"}
_TAKE_WORDS = {"взять", "поднять", "take"}
_DROP_WORDS = {"положить", "бросить", "drop"}


def parse_action(text: str, player_id: str) -> CanonicalAction | None:
    source = text.strip()
    if not source:
        return None

    parts = source.split(maxsplit=1)
    verb = parts[0].casefold()
    argument = parts[1].strip() if len(parts) == 2 else None

    if verb in _LOOK_WORDS and argument is None:
        return CanonicalAction(player_id, ActionType.LOOK, source_text=source)
    if verb in _MOVE_WORDS and argument:
        return CanonicalAction(
            player_id,
            ActionType.MOVE,
            destination_id=argument,
            source_text=source,
        )
    if verb in _TAKE_WORDS and argument:
        return CanonicalAction(
            player_id,
            ActionType.TAKE,
            target_id=argument,
            source_text=source,
        )
    if verb in _DROP_WORDS and argument:
        return CanonicalAction(
            player_id,
            ActionType.DROP,
            target_id=argument,
            source_text=source,
        )
    return None
