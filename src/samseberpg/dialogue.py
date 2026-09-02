from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

from .db import GameDatabase
from .domain import QuestState
from .npc_profiles import get_npc_profile
from .quest import QUEST_TYPE, QuestService

OFFER_PROPOSAL = f"offer_quest:{QUEST_TYPE}"
_ALLOWED_PROPOSALS = {OFFER_PROPOSAL}
REMEMBER_MIRA_WOOD_COMMITMENT = "remember_commitment:bring_useful_wood_to_mira"
_ALLOWED_SOCIAL_ACTIONS = {REMEMBER_MIRA_WOOD_COMMITMENT}
MIRA_COMMITMENT_FACT = "The player promised Mira to bring useful wood while her workshop was blocked."


@dataclass(frozen=True, slots=True)
class DialogueDecision:
    text: str
    proposal: str | None = None
    used_fallback: bool = False
    social_action: str | None = None
    npc_id: str = "npc_oren"


@dataclass(frozen=True, slots=True)
class DialogueTurn:
    user_text: str
    npc_text: str


@dataclass(frozen=True, slots=True)
class DialogueContext:
    npc_id: str
    player_id: str
    display_name: str
    role: str
    personality: str
    speech_style: str
    motivations: tuple[str, ...]
    knowledge_boundaries: tuple[str, ...]
    activity: str
    location_id: str
    trust: int
    relation: dict[str, int]
    quest: QuestState | None
    memories: tuple[str, ...]
    recent_dialogue: tuple[DialogueTurn, ...]
    runtime_state: dict[str, object]
    nearby_actors: tuple[str, ...]
    nearby_entities: tuple[str, ...]
    own_events: tuple[str, ...]
    user_text: str

    def to_prompt(self) -> str:
        history = " | ".join(
            f"player: {turn.user_text} / {self.display_name}: {turn.npc_text}"
            for turn in self.recent_dialogue
        ) or "none"
        memories = " | ".join(self.memories) or "none"
        events = " | ".join(self.own_events) or "none"
        nearby_actors = ", ".join(self.nearby_actors) or "none"
        nearby_entities = ", ".join(self.nearby_entities) or "none"
        lines = [
            f"npc_id: {self.npc_id}",
            f"npc_name: {self.display_name}",
            f"role: {self.role}",
            f"personality: {self.personality}",
            f"speech_style: {self.speech_style}",
            f"motivations: {' | '.join(self.motivations)}",
            f"knowledge_boundaries: {' | '.join(self.knowledge_boundaries)}",
            f"activity: {self.activity}",
            f"location: {self.location_id}",
            f"runtime_state: {json.dumps(self.runtime_state, ensure_ascii=False, sort_keys=True)}",
            f"relation_to_player: {json.dumps(self.relation, ensure_ascii=False, sort_keys=True)}",
            f"relevant_memories: {memories}",
            f"recent_dialogue: {history}",
            f"nearby_actors: {nearby_actors}",
            f"nearby_entities: {nearby_entities}",
            f"own_recent_events: {events}",
        ]
        if self.quest is not None:
            lines.extend(
                [
                    f"quest_status: {self.quest.status}",
                    f"firewood_owned_by_player: {self.quest.owned_firewood}/{self.quest.required_firewood}",
                ]
            )
        lines.extend(
            [
                "knowledge_rule: You know only the supplied facts. Missing facts are unknown to you.",
                f"player_says: {self.user_text}",
            ]
        )
        return "\n".join(lines)


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

    def talk(
        self,
        player_id: str,
        user_text: str,
        npc_id: str = "npc_oren",
    ) -> DialogueDecision:
        context = self.build_context(player_id, user_text, npc_id)
        if self.provider is None:
            decision = _fallback(context)
        else:
            try:
                raw = self.provider.generate(context)
                text = raw.text.strip()
                proposal = raw.proposal
                social_action = getattr(raw, "social_action", None)
                if not text:
                    decision = _fallback(context)
                elif proposal is not None and (
                    proposal not in _ALLOWED_PROPOSALS
                    or npc_id != "npc_oren"
                    or context.quest is None
                    or context.quest.status != "available"
                ):
                    decision = _fallback(context)
                elif social_action is not None and (
                    social_action not in _ALLOWED_SOCIAL_ACTIONS
                    or npc_id != "npc_mira"
                    or not bool(context.runtime_state.get("requested_wood"))
                ):
                    decision = _fallback(context)
                else:
                    decision = DialogueDecision(
                        text=text,
                        proposal=proposal,
                        used_fallback=False,
                        social_action=social_action,
                        npc_id=npc_id,
                    )
            except Exception:
                decision = _fallback(context)
        return self._apply_and_persist(context, decision)

    def _apply_and_persist(
        self, context: DialogueContext, decision: DialogueDecision
    ) -> DialogueDecision:
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            resolved = decision
            if decision.social_action == REMEMBER_MIRA_WOOD_COMMITMENT:
                row = conn.execute(
                    "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id = 'npc_mira'"
                ).fetchone()
                state = {} if row is None else json.loads(str(row[0]))
                if context.npc_id != "npc_mira" or not bool(state.get("requested_wood")):
                    resolved = _fallback(context)
                else:
                    now = _sqlite_utc_now(conn)
                    conn.execute(
                        "INSERT INTO npc_memories "
                        "(npc_actor_id, subject_actor_id, fact, importance, reinforcement_count, created_at) "
                        "VALUES ('npc_mira', ?, ?, 80, 0, ?) "
                        "ON CONFLICT(npc_actor_id, subject_actor_id, fact) DO UPDATE SET "
                        "reinforcement_count = reinforcement_count + 1",
                        (context.player_id, MIRA_COMMITMENT_FACT, now),
                    )
            player_id = context.player_id
            conn.execute(
                "INSERT INTO dialogue_turns "
                "(world_id, npc_actor_id, player_actor_id, user_text, npc_text, proposal_json, used_fallback, created_at) "
                "SELECT actors.world_id, ?, ?, ?, ?, ?, ?, ? FROM actors WHERE actors.id = ?",
                (
                    context.npc_id,
                    player_id,
                    context.user_text,
                    resolved.text,
                    json.dumps(
                        {"proposal": resolved.proposal, "social_action": resolved.social_action},
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    int(resolved.used_fallback),
                    _sqlite_utc_now(conn),
                    player_id,
                ),
            )
            conn.execute("COMMIT")
            return DialogueDecision(
                text=resolved.text,
                proposal=resolved.proposal,
                used_fallback=resolved.used_fallback,
                social_action=resolved.social_action,
                npc_id=context.npc_id,
            )
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def build_context(
        self,
        player_id: str,
        user_text: str = "",
        npc_id: str = "npc_oren",
    ) -> DialogueContext:
        profile = get_npc_profile(npc_id)
        conn = self.db.connect()
        try:
            player = conn.execute(
                "SELECT location_id FROM actors WHERE id = ? AND actor_type = 'player'",
                (player_id,),
            ).fetchone()
            if player is None:
                raise LookupError(f"player not found: {player_id}")
            npc = conn.execute(
                "SELECT npcs.role, npcs.current_activity, actors.location_id "
                "FROM npcs JOIN actors ON actors.id = npcs.actor_id "
                "WHERE npcs.actor_id = ?",
                (npc_id,),
            ).fetchone()
            if npc is None:
                raise LookupError(f"NPC not found: {npc_id}")
            player_location = str(player[0])
            npc_location = str(npc[2])
            if player_location != npc_location:
                raise LookupError(f"NPC not present with player: {npc_id}")

            relation_row = conn.execute(
                "SELECT familiarity, trust, affinity, fear, conflict, romance "
                "FROM relations WHERE source_actor_id = ? AND target_actor_id = ?",
                (npc_id, player_id),
            ).fetchone()
            relation_keys = (
                "familiarity",
                "trust",
                "affinity",
                "fear",
                "conflict",
                "romance",
            )
            relation = (
                {key: 0 for key in relation_keys}
                if relation_row is None
                else {
                    key: int(relation_row[index])
                    for index, key in enumerate(relation_keys)
                }
            )

            memories = tuple(
                str(row[0])
                for row in conn.execute(
                    "SELECT fact FROM npc_memories "
                    "WHERE npc_actor_id = ? AND subject_actor_id = ? "
                    "ORDER BY importance DESC, reinforcement_count DESC, created_at DESC LIMIT 5",
                    (npc_id, player_id),
                ).fetchall()
            )
            recent_rows = conn.execute(
                "SELECT user_text, npc_text FROM dialogue_turns "
                "WHERE npc_actor_id = ? AND player_actor_id = ? "
                "ORDER BY id DESC LIMIT 6",
                (npc_id, player_id),
            ).fetchall()
            recent_dialogue = tuple(
                DialogueTurn(user_text=str(row[0]), npc_text=str(row[1]))
                for row in reversed(recent_rows)
            )
            runtime_row = conn.execute(
                "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id = ?",
                (npc_id,),
            ).fetchone()
            runtime_state = (
                {} if runtime_row is None else json.loads(str(runtime_row[0]))
            )

            nearby_actors = tuple(
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM actors "
                    "WHERE location_id = ? AND id <> ? ORDER BY name",
                    (npc_location, npc_id),
                ).fetchall()
            )
            nearby_entities = tuple(
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM entities WHERE location_id = ? ORDER BY name",
                    (npc_location,),
                ).fetchall()
            )
            event_rows = conn.execute(
                "SELECT event_type, summary FROM world_events "
                "WHERE actor_id = ? ORDER BY id DESC LIMIT 5",
                (npc_id,),
            ).fetchall()
            own_events = tuple(
                f"{row[0]}: {row[1]}" for row in reversed(event_rows)
            )
        finally:
            conn.close()

        quest_state = self.quest.get_state(player_id) if npc_id == "npc_oren" else None
        return DialogueContext(
            npc_id=npc_id,
            player_id=player_id,
            display_name=profile.display_name,
            role=str(npc[0]),
            personality=profile.personality,
            speech_style=profile.speech_style,
            motivations=profile.motivations,
            knowledge_boundaries=profile.knowledge_boundaries,
            activity=str(npc[1]),
            location_id=npc_location,
            trust=relation["trust"],
            relation=relation,
            quest=quest_state,
            memories=memories,
            recent_dialogue=recent_dialogue,
            runtime_state=runtime_state,
            nearby_actors=nearby_actors,
            nearby_entities=nearby_entities,
            own_events=own_events,
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
        display_name = getattr(context, "display_name", "Орен")
        npc_id = getattr(context, "npc_id", "npc_oren")
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                f"You are {display_name}, a grounded NPC in a small remote fantasy village. "
                "Speak naturally and briefly in Russian, following the supplied personality and speech style. "
                "Use only the supplied world state and knowledge. Never invent inventory, rewards, completed actions, "
                "locations, private conversations or world facts. The proposal field may only offer the existing "
                "bring_5_firewood quest when you are Oren and the supplied state permits it; otherwise use none."
            ),
            input=context.to_prompt(),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "living_npc_dialogue",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "proposal": {
                                "type": "string",
                                "enum": [OFFER_PROPOSAL, "none"],
                            },
                            "social_action": {
                                "type": "string",
                                "enum": [REMEMBER_MIRA_WOOD_COMMITMENT, "none"],
                            },
                        },
                        "required": ["text", "proposal", "social_action"],
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
        social_action = payload.get("social_action", "none")
        if social_action == "none":
            social_action = None
        elif social_action not in _ALLOWED_SOCIAL_ACTIONS:
            raise ValueError(f"invalid dialogue social action: {social_action}")
        return DialogueDecision(
            text=str(payload["text"]),
            proposal=proposal,
            social_action=social_action,
            npc_id=npc_id,
        )


def _fallback(context: DialogueContext) -> DialogueDecision:
    if context.npc_id == "npc_mira":
        if bool(context.runtime_state.get("requested_wood")):
            if _is_mira_wood_commitment(context.user_text):
                return DialogueDecision(
                    text="Мира коротко кивает: «Договорились. Принесёшь древесину — я продолжу работу.»",
                    used_fallback=True,
                    social_action=REMEMBER_MIRA_WOOD_COMMITMENT,
                    npc_id=context.npc_id,
                )
            return DialogueDecision(
                text="Мира отрывается от верстака: «Работа встала. Нужна пригодная древесина, а запас кончился.»",
                used_fallback=True,
                npc_id=context.npc_id,
            )
        return DialogueDecision(
            text="Мира не прекращает работу: «Пока всё идёт. Если что-то понадобится — скажу.»",
            used_fallback=True,
            npc_id=context.npc_id,
        )
    if context.npc_id == "npc_kaspar":
        if int(context.runtime_state.get("carrying_wood", 0) or 0) > 0:
            return DialogueDecision(
                text="Каспар кивает на древесину: «Нашёл, что нужно. Теперь бы донести.»",
                used_fallback=True,
                npc_id=context.npc_id,
            )
        if context.runtime_state.get("goal"):
            return DialogueDecision(
                text="Каспар бросает взгляд в сторону тропы: «Есть одно дело. Само себя оно не сделает.»",
                used_fallback=True,
                npc_id=context.npc_id,
            )
        return DialogueDecision(
            text="Каспар пожимает плечами: «Проверяю берег. Иногда река приносит вещи полезнее разговоров.»",
            used_fallback=True,
            npc_id=context.npc_id,
        )

    state = context.quest
    if state is None:
        return DialogueDecision(
            text="Орен молча кивает.",
            used_fallback=True,
            npc_id=context.npc_id,
        )
    if state.status == "available":
        return DialogueDecision(
            text="Орен кивает на почти пустую поленницу: «Если не трудно, принеси мне пять поленьев дров со двора мастерской.»",
            proposal=OFFER_PROPOSAL,
            used_fallback=True,
            npc_id=context.npc_id,
        )
    if state.status == "active" and state.owned_firewood < state.required_firewood:
        return DialogueDecision(
            text=f"«Мне нужны все пять поленьев. Сейчас у тебя {state.owned_firewood} из {state.required_firewood}.»",
            used_fallback=True,
            npc_id=context.npc_id,
        )
    if state.status == "active":
        return DialogueDecision(
            text="Орен замечает охапку: «Вот и все пять. Давай сюда — как раз вовремя.»",
            used_fallback=True,
            npc_id=context.npc_id,
        )
    return DialogueDecision(
        text="Орен улыбается чуть теплее: «Спасибо за те дрова. Я помню, что ты выручил меня.»",
        used_fallback=True,
        npc_id=context.npc_id,
    )


def _sqlite_utc_now(conn) -> str:
    return str(
        conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").fetchone()[0]
    )


def _is_mira_wood_commitment(user_text: str) -> bool:
    text = user_text.lower()
    promises = ("принесу", "принести", "достану", "найду", "притащу")
    resources = ("древес", "дерев", "коряг", "wood")
    return any(token in text for token in promises) and any(
        token in text for token in resources
    )
