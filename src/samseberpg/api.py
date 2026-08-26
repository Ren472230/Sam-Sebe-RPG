from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .dialogue import DialogueService
from .domain import ActionType, CanonicalAction
from .game import GameService
from .quest import QuestService


class SessionRequest(BaseModel):
    external_id: str = "local-player"
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
    text: str | None = None
    user_text: str | None = None

    def resolved_text(self) -> str:
        if self.text is not None:
            return self.text
        return self.user_text or ""


def create_app(game: GameService, quest: QuestService, dialogue: DialogueService) -> FastAPI:
    app = FastAPI(title="Sam-Sebe-RPG Vertical Slice")

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
            return asdict(dialogue.talk(request.player_id, request.resolved_text()))
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
