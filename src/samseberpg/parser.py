from __future__ import annotations

import shlex

from .domain import ActionType, CanonicalAction


def parse_command(text: str, player_id: str = "player_1") -> CanonicalAction | None:
    source = text.strip()
    if not source:
        return None

    try:
        tokens = shlex.split(source)
    except ValueError:
        return None
    if not tokens:
        return None

    lowered = [token.casefold() for token in tokens]

    if lowered in (["осмотреться"], ["осмотр"], ["look"]):
        return CanonicalAction(player_id, ActionType.LOOK, source_text=source)

    if lowered[0] in {"идти", "перейти", "move", "go"} and len(tokens) == 2:
        return CanonicalAction(
            player_id,
            ActionType.MOVE,
            destination_id=tokens[1],
            source_text=source,
        )

    if lowered[0] in {"взять", "поднять", "take"} and len(tokens) == 2:
        return CanonicalAction(
            player_id,
            ActionType.TAKE,
            item_id=tokens[1],
            source_text=source,
        )

    if lowered[0] in {"оставить", "положить", "drop"} and len(tokens) == 2:
        return CanonicalAction(
            player_id,
            ActionType.DROP,
            item_id=tokens[1],
            source_text=source,
        )

    if lowered[0] in {"ждать", "wait"}:
        ticks = 1
        if len(tokens) == 2:
            try:
                ticks = int(tokens[1])
            except ValueError:
                return None
        elif len(tokens) != 1:
            return None
        return CanonicalAction(
            player_id,
            ActionType.WAIT,
            modifiers={"ticks": ticks},
            source_text=source,
        )

    aimed = False
    throw_start = 0
    if len(lowered) >= 2 and lowered[0] in {"прицельно", "aimed"} and lowered[1] in {
        "бросить",
        "throw",
    }:
        aimed = True
        throw_start = 1

    if len(lowered) > throw_start and lowered[throw_start] in {"бросить", "throw"}:
        remainder = tokens[throw_start + 1 :]
        remainder_lower = lowered[throw_start + 1 :]
        if len(remainder) == 3 and remainder_lower[1] in {"в", "at", "into"}:
            modifiers = {"aimed": True} if aimed else {}
            return CanonicalAction(
                player_id,
                ActionType.THROW,
                target_id=remainder[2],
                item_id=remainder[0],
                modifiers=modifiers,
                source_text=source,
            )

    return None
