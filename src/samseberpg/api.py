from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .db import DEFAULT_WORLD_ID
from .dialogue import DialogueService
from .domain import ActionType, CanonicalAction
from .game import GameService
from .playtest import PlaytestService
from .quest import QuestService


class SessionRequest(BaseModel):
    external_id: str = "local-player"
    name: str = "Player"


class ActionRequest(BaseModel):
    player_id: str
    action_type: ActionType
    target_id: str | None = None
    recipient_id: str | None = None
    destination_id: str | None = None
    source_text: str | None = None
    modifiers: Any | None = None
    external_id: str | None = None


class QuestRequest(BaseModel):
    player_id: str
    external_id: str | None = None


class DialogueRequest(BaseModel):
    player_id: str
    text: str | None = None
    user_text: str | None = None

    def resolved_text(self) -> str:
        if self.text is not None:
            return self.text
        return self.user_text or ""


class PlaytestEventRequest(BaseModel):
    session_id: str
    player_id: str | None = None
    event_type: str
    success: bool = True
    summary: str = ""
    evidence: dict[str, Any] | None = None


def create_app(game: GameService, quest: QuestService, dialogue: DialogueService) -> FastAPI:
    app = FastAPI(title="Sam-Sebe-RPG Vertical Slice")
    playtest = PlaytestService(game.db, game.clock)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/session")
    def create_session(request: SessionRequest) -> dict[str, str]:
        external_id = request.external_id.strip() or "local-player"
        player_id = game.register_player(external_id, request.name.strip() or "Player")
        return {"player_id": player_id}

    @app.get("/api/state/{player_id}")
    def state(player_id: str):
        try:
            view = game.observe(player_id)
            quest_state = quest.get_state(player_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        coins, relation = _economy_and_oren_relation(game, player_id)
        world = asdict(view)
        return {
            "player_id": view.player_id,
            "location": {
                "id": view.location_id,
                "name": view.location_name,
                "description": view.location_description,
            },
            "visible_actors": [asdict(actor) for actor in view.visible_actors],
            "visible_entities": [asdict(entity) for entity in view.visible_entities],
            "inventory": [asdict(entity) for entity in view.inventory],
            "quest": asdict(quest_state),
            "coins": coins,
            "oren_relation": relation,
            "world": world,
            "oren_trust": relation["trust"],
            "world_pulse": _world_pulse(game),
        }

    @app.post("/api/action")
    def action(request: ActionRequest):
        result = game.execute(
            CanonicalAction(
                actor_id=request.player_id,
                action_type=request.action_type,
                target_id=request.target_id,
                recipient_id=request.recipient_id,
                destination_id=request.destination_id,
                source_text=request.source_text,
                modifiers=request.modifiers,
            ),
            external_id=request.external_id,
        )
        return asdict(result)

    @app.post("/api/quest/accept")
    def accept_quest(request: QuestRequest):
        try:
            return asdict(quest.accept(request.player_id, request.external_id))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/quest/turn-in")
    def turn_in_quest(request: QuestRequest):
        try:
            return asdict(quest.turn_in(request.player_id, request.external_id))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/dialogue")
    def npc_dialogue(request: DialogueRequest):
        try:
            return asdict(dialogue.talk(request.player_id, request.resolved_text()))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/playtest/event")
    def record_playtest_event(request: PlaytestEventRequest) -> dict[str, int]:
        try:
            event_id = playtest.record(
                request.session_id,
                request.event_type,
                player_id=request.player_id,
                success=request.success,
                summary=request.summary,
                evidence=request.evidence,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"event_id": event_id}

    @app.get("/api/playtest/report/{session_id}")
    def playtest_report(session_id: str, commit: str | None = None):
        try:
            return playtest.report(session_id, commit=commit)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


def _economy_and_oren_relation(
    game: GameService, player_id: str
) -> tuple[int, dict[str, int]]:
    with game.db.connect() as conn:
        player = conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?", (player_id,)
        ).fetchone()
        if player is None:
            raise LookupError(f"player not found: {player_id}")
        row = conn.execute(
            "SELECT familiarity, trust, affinity, fear, conflict, romance "
            "FROM relations WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?",
            (player_id,),
        ).fetchone()

    keys = ("familiarity", "trust", "affinity", "fear", "conflict", "romance")
    relation = (
        {key: 0 for key in keys}
        if row is None
        else {key: int(row[index]) for index, key in enumerate(keys)}
    )
    return int(player[0]), relation


def _world_pulse(game: GameService) -> dict[str, object]:
    with game.db.connect() as conn:
        runtime = conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?",
            (DEFAULT_WORLD_ID,),
        ).fetchone()
        rows = conn.execute(
            "SELECT tick, actor_id, event_type, summary FROM world_events "
            "WHERE world_id = ? ORDER BY id DESC LIMIT 5",
            (DEFAULT_WORLD_ID,),
        ).fetchall()

    tick = 0 if runtime is None else int(runtime[0])
    latest_events = [
        {
            "tick": int(row[0]),
            "actor_id": str(row[1]),
            "event_type": str(row[2]),
            "summary": str(row[3]),
        }
        for row in reversed(rows)
    ]
    return {"tick": tick, "latest_events": latest_events}
