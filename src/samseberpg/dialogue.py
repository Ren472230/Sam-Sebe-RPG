from __future__ import annotations

from dataclasses import dataclass

from .domain import ActionResult
from .game import GameService


@dataclass(frozen=True, slots=True)
class NpcPersona:
    npc_id: str
    name: str
    neutral_stage: str
    warm_stage: str
    familiar_stage: str
    guarded_stage: str


PERSONAS = {
    "npc_mira": NpcPersona(
        "npc_mira",
        "Мира",
        "Мира на секунду отрывается от работы и переводит взгляд на вас.",
        "Мира замечает вас и тепло улыбается краешком губ.",
        "Мира кивает вам уже без прежней осторожности.",
        "Мира перестаёт работать и смотрит на вас заметно настороженнее.",
    ),
    "npc_oren": NpcPersona(
        "npc_oren",
        "Орен",
        "Орен оценивающе смотрит на вас через стойку.",
        "Орен при вашем появлении заметно смягчается.",
        "Орен приветствует вас коротким знакомым кивком.",
        "Орен смотрит настороженно и не спешит сокращать дистанцию после недавнего шума.",
    ),
    "npc_kaspar": NpcPersona(
        "npc_kaspar",
        "Каспар",
        "Каспар поднимает взгляд, будто вырванный из собственных мыслей.",
        "Каспар встречает вас редкой, но вполне искренней улыбкой.",
        "Каспар узнаёт вас сразу и отвечает без лишних церемоний.",
        "Каспар становится молчаливее обычного и внимательно следит за вами.",
    ),
}


class DialogueService:
    """Read-only dialogue renderer over canonical TALK and relationship state."""

    def __init__(self, game: GameService):
        self.game = game

    def render(self, player_id: str, talk_result: ActionResult) -> str:
        if not talk_result.success:
            return ""
        target_id = talk_result.data.get("target_id")
        if not isinstance(target_id, str) or target_id not in PERSONAS:
            return ""

        with self.game.db.connect() as conn:
            target = conn.execute(
                """
                SELECT a.name, n.current_activity
                FROM actors a
                JOIN npcs n ON n.actor_id = a.id
                WHERE a.id = ?
                """,
                (target_id,),
            ).fetchone()
            if target is None:
                return ""
            relation = conn.execute(
                """
                SELECT familiarity, trust, affinity, conflict
                FROM relations
                WHERE source_actor_id = ? AND target_actor_id = ?
                """,
                (target_id, player_id),
            ).fetchone()

        familiarity = int(relation["familiarity"]) if relation is not None else 0
        trust = int(relation["trust"]) if relation is not None else 0
        affinity = int(relation["affinity"]) if relation is not None else 0
        conflict = int(relation["conflict"]) if relation is not None else 0
        persona = PERSONAS[target_id]

        if conflict >= 4 or trust <= -3:
            stage = persona.guarded_stage
            speech = "— Говори. Только давай сегодня без новых проблем."
        elif trust >= 2 or affinity >= 1:
            stage = persona.warm_stage
            speech = "— Рад тебя видеть. Что у тебя?"
        elif familiarity >= 3:
            stage = persona.familiar_stage
            speech = "— Снова ты. Ну, рассказывай."
        else:
            stage = persona.neutral_stage
            speech = "— Если по делу — говори."

        utterance = str(talk_result.data.get("utterance") or "").casefold()
        activity = str(talk_result.data.get("npc_activity") or target["current_activity"])
        if "как дела" in utterance or "чем занима" in utterance or "what are you doing" in utterance:
            speech = f"— Сейчас {activity}. А что?"
            if conflict >= 4 or trust <= -3:
                speech += " И давай без нового шума."

        return f"**{persona.name}**\n*{stage}*\n{speech}"
