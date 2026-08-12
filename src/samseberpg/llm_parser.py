from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .db import GameDatabase
from .domain import ActionType, CanonicalAction
from .world import LOCATION_GRAPH


IMPLEMENTED_ACTIONS = {
    ActionType.LOOK,
    ActionType.MOVE,
    ActionType.TAKE,
    ActionType.DROP,
    ActionType.THROW,
    ActionType.WAIT,
}

ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recognized": {"type": "boolean"},
        "action_type": {
            "type": "string",
            "enum": [
                action.value
                for action in sorted(IMPLEMENTED_ACTIONS, key=lambda item: item.value)
            ],
        },
        "target_id": {"type": ["string", "null"]},
        "item_id": {"type": ["string", "null"]},
        "destination_id": {"type": ["string", "null"]},
        "aimed": {"type": "boolean"},
        "ticks": {"type": "integer", "minimum": 1, "maximum": 100},
    },
    "required": [
        "recognized",
        "action_type",
        "target_id",
        "item_id",
        "destination_id",
        "aimed",
        "ticks",
    ],
    "additionalProperties": False,
}

Transport = Callable[[str, dict[str, object], float], dict[str, object]]


class OllamaParserError(RuntimeError):
    """Raised when the optional local Ollama parser cannot return valid JSON."""


def build_parser_context(
    db: GameDatabase, player_id: str = "player_1"
) -> dict[str, object]:
    player = db.fetch_player(player_id)
    if player is None:
        raise ValueError(f"Unknown player: {player_id}")
    location_id = player["location_id"]
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT entity_id, entity_type, name
            FROM entities
            WHERE location_id = ?
            ORDER BY entity_type, entity_id
            """,
            (location_id,),
        ).fetchall()
    return {
        "location_id": location_id,
        "exits": sorted(LOCATION_GRAPH.get(location_id, set())),
        "inventory": db.list_inventory(player_id),
        "visible_entities": [dict(row) for row in rows],
    }


def _http_transport(
    url: str, payload: dict[str, object], timeout: float
) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise OllamaParserError(f"Ollama request failed: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaParserError("Ollama returned invalid JSON envelope") from exc
    if not isinstance(parsed, dict):
        raise OllamaParserError("Ollama returned a non-object response")
    return parsed


@dataclass(slots=True)
class OllamaActionParser:
    model: str
    base_url: str = "http://localhost:11434"
    timeout: float = 45.0
    transport: Transport = _http_transport

    def parse(
        self,
        text: str,
        context: dict[str, object],
        player_id: str = "player_1",
    ) -> CanonicalAction | None:
        prompt_context = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        payload: dict[str, object] = {
            "model": self.model,
            "stream": False,
            "format": ACTION_SCHEMA,
            "options": {"temperature": 0},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты parser намерения игрока для детерминированной RPG. "
                        "Ты не решаешь исход действия и не меняешь мир. "
                        "Верни только структуру, соответствующую JSON schema. "
                        "Используй только action_type из schema и только ID из переданного контекста, "
                        "если они нужны. Если действие нельзя выразить текущим игровым языком, "
                        "поставь recognized=false."
                    ),
                },
                {
                    "role": "user",
                    "content": f"WORLD_CONTEXT={prompt_context}\nPLAYER_INPUT={text}",
                },
            ],
        }
        envelope = self.transport(
            self.base_url.rstrip("/") + "/api/chat", payload, self.timeout
        )
        try:
            message = envelope["message"]
            if not isinstance(message, dict):
                raise TypeError
            content = message["content"]
            if not isinstance(content, str):
                raise TypeError
            data = json.loads(content)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise OllamaParserError("Ollama returned invalid structured content") from exc

        if not isinstance(data, dict) or data.get("recognized") is not True:
            return None

        try:
            action_type = ActionType(str(data.get("action_type")))
        except ValueError:
            return None
        if action_type not in IMPLEMENTED_ACTIONS:
            return None

        modifiers: dict[str, object] = {}
        if action_type == ActionType.THROW and data.get("aimed") is True:
            modifiers["aimed"] = True
        if action_type == ActionType.WAIT:
            ticks = data.get("ticks", 1)
            if not isinstance(ticks, int) or isinstance(ticks, bool):
                return None
            modifiers["ticks"] = ticks

        def optional_string(key: str) -> str | None:
            value = data.get(key)
            return value if isinstance(value, str) and value else None

        return CanonicalAction(
            actor_id=player_id,
            action_type=action_type,
            target_id=optional_string("target_id"),
            item_id=optional_string("item_id"),
            destination_id=optional_string("destination_id"),
            modifiers=modifiers,
            source_text=text,
        )
