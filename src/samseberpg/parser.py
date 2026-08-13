from __future__ import annotations

import re

from .domain import ActionType, CanonicalAction


_THROW_RE = re.compile(
    r"^(?:бросить|throw)\s+(\S+)\s+(?:в|at)\s+(\S+)$", re.IGNORECASE
)
_AIMED_THROW_RE = re.compile(
    r"^(?:прицельно\s+бросить|aimed\s+throw)\s+(\S+)\s+(?:в|at)\s+(\S+)$",
    re.IGNORECASE,
)
_LODGING_RE = re.compile(
    r"^(?:спросить|ask)\s+(\S+)\s+(?:о\s+ночлеге|about\s+lodging)$",
    re.IGNORECASE,
)
_GIVE_RE = re.compile(r"^(?:дать|give)\s+(\S+)\s+(\S+)$", re.IGNORECASE)
_FEED_RE = re.compile(r"^(?:покормить|feed)\s+(\S+)\s+(\S+)$", re.IGNORECASE)


def parse_command(text: str, player_id: str = "player_1") -> CanonicalAction | None:
    source = text.strip()
    normalized = source.lower()
    if not normalized:
        return None

    if normalized in {"осмотреться", "осмотр", "look", "смотреть"}:
        return CanonicalAction(player_id, ActionType.LOOK, source_text=source)

    if normalized in {"оплатить ночлег", "заплатить за ночлег", "pay lodging"}:
        return CanonicalAction(
            player_id,
            ActionType.TALK,
            target_id="oren_innkeeper",
            modifiers={"topic": "pay_lodging"},
            source_text=source,
        )
    if normalized in {"попросить ночлег", "request lodging"}:
        return CanonicalAction(
            player_id,
            ActionType.TALK,
            target_id="oren_innkeeper",
            modifiers={"topic": "request_lodging"},
            source_text=source,
        )

    lodging_match = _LODGING_RE.match(source)
    if lodging_match:
        return CanonicalAction(
            player_id,
            ActionType.TALK,
            target_id=lodging_match.group(1),
            modifiers={"topic": "lodging"},
            source_text=source,
        )

    for prefix in ("поговорить ", "talk "):
        if normalized.startswith(prefix):
            return CanonicalAction(
                player_id,
                ActionType.TALK,
                target_id=source[len(prefix) :].strip(),
                source_text=source,
            )

    give_match = _GIVE_RE.match(source)
    if give_match:
        item_id, target_id = give_match.groups()
        return CanonicalAction(
            player_id,
            ActionType.GIVE,
            target_id=target_id,
            item_id=item_id,
            source_text=source,
        )

    feed_match = _FEED_RE.match(source)
    if feed_match:
        target_id, item_id = feed_match.groups()
        return CanonicalAction(
            player_id,
            ActionType.FEED,
            target_id=target_id,
            item_id=item_id,
            source_text=source,
        )

    for prefix in ("идти ", "move "):
        if normalized.startswith(prefix):
            return CanonicalAction(
                player_id,
                ActionType.MOVE,
                destination_id=source[len(prefix) :].strip(),
                source_text=source,
            )

    for prefix in ("взять ", "take "):
        if normalized.startswith(prefix):
            return CanonicalAction(
                player_id,
                ActionType.TAKE,
                item_id=source[len(prefix) :].strip(),
                source_text=source,
            )

    for prefix in ("бросить_на_землю ", "drop "):
        if normalized.startswith(prefix):
            return CanonicalAction(
                player_id,
                ActionType.DROP,
                item_id=source[len(prefix) :].strip(),
                source_text=source,
            )

    if normalized in {"ждать", "wait"}:
        return CanonicalAction(
            player_id,
            ActionType.WAIT,
            modifiers={"ticks": 1},
            source_text=source,
        )
    for prefix in ("ждать ", "wait "):
        if normalized.startswith(prefix):
            try:
                ticks = int(normalized[len(prefix) :].strip())
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
