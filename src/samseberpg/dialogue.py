from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

from .db import GameDatabase
from .domain import QuestState
from .quest import QUEST_TYPE, QuestService

OFFER_PROPOSAL = f"offer_quest:{QUEST_TYPE}"
_ALLOWED_PROPOSALS = {OFFER_PROPOSAL}


@dataclass(frozen=True, slots=True)
class DialogueDecision:
    text: str
    proposal: str | None = None
    used_fallback: bool = False


@dataclass(frozen=True, slots=True)
class DialogueContext:
    npc_id: str
    role: str
    activity: str
    location_id: str
    trust: int
    quest: QuestState
    memories: tuple[str, ...]
    user_text: str

    def to_prompt(self) -> str:
        memory_text = " | ".join(self.memories) if self.memories else "none"
        return (
            "NPC: Oren\n"
            f"role: {self.role}\n"
            f"activity: {self.activity}\n"
            f"location: {self.location_id}\n"
            f"trust_to_player: {self.trust}\n"
            f"quest_status: {self.quest.status}\n"
            f"firewood_owned_by_player: {self.quest.owned_firewood}/{self.quest.required_firewood}\n"
            f"relevant_memories: {memory_text}\n"
            f"player_says: {self.user_text}"
        )


class DialogueProvider(Protocol):
    def generate(self, context: DialogueContext) -> DialogueDecision: ...


class DialogueService:
    def __init__(
        self,
        db: GameDatabase,
        quest: QuestService,
        *,
        provider: DialogueProvider | None = None,
    ) -> None:
        self.db = db
        self.quest = quest
        self.provider = provider

    def talk(self, player_id: str, user_text: str) -> DialogueDecision:
        context = self.build_context(player_id, user_text)
        if self.provider is None:
            return _fallback(context)
        try:
            decision = self.provider.generate(context)
            text = decision.text.strip()
            proposal = decision.proposal
            if not text:
                return _fallback(context)
            if proposal is not None:
                if proposal not in _ALLOWED_PROPOSALS:
                    return _fallback(context)
                if proposal == OFFER_PROPOSAL and context.quest.status != "available":
                    return _fallback(context)
        except Exception:
            return _fallback(context)
        return DialogueDecision(text=text, proposal=proposal, used_fallback=False)

    def build_context(self, player_id: str, user_text: str = "") -> DialogueContext:
        quest_state = self.quest.get_state(player_id)
        conn = self.db.connect()
        try:
            npc = conn.execute(
                "SELECT npcs.role, npcs.current_activity, actors.location_id "
                "FROM npcs JOIN actors ON actors.id = npcs.actor_id "
                "WHERE npcs.actor_id = 'npc_oren'"
            ).fetchone()
            if npc is None:
                raise LookupError("Oren not found")
            relation = conn.execute(
                "SELECT trust FROM relations "
                "WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?",
                (player_id,),
            ).fetchone()
            memories = conn.execute(
                "SELECT fact FROM npc_memories "
                "WHERE npc_actor_id = 'npc_oren' AND subject_actor_id = ? "
                "ORDER BY importance DESC, reinforcement_count DESC, created_at DESC LIMIT 5",
                (player_id,),
            ).fetchall()
        finally:
            conn.close()
        return DialogueContext(
            npc_id="npc_oren",
            role=str(npc[0]),
            activity=str(npc[1]),
            location_id=str(npc[2]),
            trust=0 if relation is None else int(relation[0]),
            quest=quest_state,
            memories=tuple(str(row[0]) for row in memories),
            user_text=user_text.strip(),
        )


class OpenAIResponsesProvider:
    def __init__(self, *, client=None, model: str | None = None) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.client = client
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5")

    def generate(self, context: DialogueContext) -> DialogueDecision:
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "You are Oren, a grounded innkeeper in a small remote fantasy village. "
                "Speak naturally and briefly in Russian. Use only the supplied world state. "
                "Never invent inventory, rewards, completed actions or world facts. "
                "The proposal field may only offer bring_5_firewood when appropriate; otherwise use none."
            ),
            input=context.to_prompt(),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "oren_dialogue",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "proposal": {
                                "type": "string",
                                "enum": [OFFER_PROPOSAL, "none"],
                            },
                        },
                        "required": ["text", "proposal"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        payload = json.loads(response.output_text)
        proposal = payload["proposal"]
        if proposal == "none":
            proposal = None
        elif proposal not in _ALLOWED_PROPOSALS:
            raise ValueError(f"invalid dialogue proposal: {proposal}")
        return DialogueDecision(text=str(payload["text"]), proposal=proposal)


def _fallback(context: DialogueContext) -> DialogueDecision:
    state = context.quest
    if state.status == "available":
        return DialogueDecision(
            text="Орен кивает на почти пустую поленницу: «Если не трудно, принеси мне пять поленьев дров со двора мастерской.»",
            proposal=OFFER_PROPOSAL,
            used_fallback=True,
        )
    if state.status == "active" and state.owned_firewood < state.required_firewood:
        return DialogueDecision(
            text=f"«Мне нужны все пять поленьев. Сейчас у тебя {state.owned_firewood} из {state.required_firewood}.»",
            used_fallback=True,
        )
    if state.status == "active":
        return DialogueDecision(
            text="Орен замечает охапку: «Вот и все пять. Давай сюда — как раз вовремя.»",
            used_fallback=True,
        )
    return DialogueDecision(
        text="Орен улыбается чуть теплее: «Спасибо за те дрова. Я помню, что ты выручил меня.»",
        used_fallback=True,
    )
