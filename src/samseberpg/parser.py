from __future__ import annotations

import re

from .domain import ActionType, CanonicalAction


_THROW_RE = re.compile(r"^(?:бросить|throw)\s+(\S+)\s+(?:в|at)\s+(\S+)$", re.IGNORECASE)
_AIMED_THROW_RE = re.compile(
    r"^(?:прицельно\s+бросить|aimed\s+throw)\s+(\S+)\s+(?:в|at)\s+(\S+)$",
    re.IGNORECASE,
)


def parse_command(text: str, player_id: str = "player_1") -> CanonicalAction | None:
    source = text.strip()
    normalized = source.lower()
    if not normalized:
        return None

    if normalized in {"осмотреться", "осмотр", "look", "смотреть"}:
        return CanonicalAction(player_id, ActionType.LOOK, source_text=source)

    for prefix in ("идти ", "move "):
        if normalized.startswith(prefix):
            destination = source[len(prefix) :].strip()
            return CanonicalAction(
                player_id,
                ActionType.MOVE,
                destination_id=destination,
                source_text=source,
            )

    for prefix in ("взять ", "take "):
        if normalized.startswith(prefix):
            item_id = source[len(prefix) :].strip()
            return CanonicalAction(
                player_id, ActionType.TAKE, item_id=item_id, source_text=source
            )

    for prefix in ("бросить_на_землю ", "drop "):
        if normalized.startswith(prefix):
            item_id = source[len(prefix) :].strip()
            return CanonicalAction(
                player_id, ActionType.DROP, item_id=item_id, source_text=source
            )

    if normalized == "ждать" or normalized == "wait":
        return CanonicalAction(
            player_id, ActionType.WAIT, modifiers={"ticks": 1}, source_text=source
        )
    for prefix in ("ждать ", "wait "):
        if normalized.startswith(prefix):
            raw_ticks = normalized[len(prefix) :].strip()
            try:
                ticks = int(raw_ticks)
            except ValueError:
                return None
            return CanonicalAction(
                player_id,
                ActionType.WAIT,
                modifiers={"ticks": ticks},
                source_text=source,
            )

    aimed_match = _AIMED_THROW_RE.match(source)
    if aimed_match:
        item_id, target_id = aimed_match.groups()
        return CanonicalAction(
            player_id,
            ActionType.THROW,
            item_id=item_id,
            target_id=target_id,
            modifiers={"aimed": True},
            source_text=source,
        )

    throw_match = _THROW_RE.match(source)
    if throw_match:
        item_id, target_id = throw_match.groups()
        return CanonicalAction(
            player_id,
            ActionType.THROW,
            item_id=item_id,
            target_id=target_id,
            source_text=source,
        )

    return None
