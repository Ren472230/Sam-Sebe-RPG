from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .dialogue import DialogueService
from .domain import ActionType, CanonicalAction
from .game import GameService
from .quest import QuestService


class SessionRequest(BaseModel):
    name: str = "Player"


class ActionRequest(BaseModel):
    player_id: str
    action_type: ActionType
    target_id: str | None = None
    destination_id: str | None = None
    source_text: str | None = None
    external_id: str | None = None


class QuestRequest(BaseModel):
    player_id: str
    external_id: str | None = None


class DialogueRequest(BaseModel):
    player_id: str
    user_text: str = ""


def create_app(game: GameService, quest: QuestService, dialogue: DialogueService) -> FastAPI:
    app = FastAPI(title="Sam-Sebe-RPG Vertical Slice")

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/session")
    def create_session(request: SessionRequest) -> dict[str, str]:
        player_id = game.register_player("local-player", request.name.strip() or "Player")
        return {"player_id": player_id}

    @app.get("/api/state/{player_id}")
    def state(player_id: str):
        try:
            view = game.observe(player_id)
            quest_state = quest.get_state(player_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        with game.db.connect() as conn:
            player = conn.execute(
                "SELECT coins FROM players WHERE actor_id = ?", (player_id,)
            ).fetchone()
            relation = conn.execute(
                "SELECT trust FROM relations WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?",
                (player_id,),
            ).fetchone()
        return {
            "world": asdict(view),
            "quest": asdict(quest_state),
            "coins": int(player[0]),
            "oren_trust": 0 if relation is None else int(relation[0]),
        }

    @app.post("/api/action")
    def action(request: ActionRequest):
        result = game.execute(
            CanonicalAction(
                actor_id=request.player_id,
                action_type=request.action_type,
                target_id=request.target_id,
                destination_id=request.destination_id,
                source_text=request.source_text,
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
            return asdict(dialogue.talk(request.player_id, request.user_text))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app
