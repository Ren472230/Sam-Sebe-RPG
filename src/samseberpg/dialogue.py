from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

from .conversation_initiative import ConversationInitiative, resolve_initiative
from .conversation_state import (
    NpcConversationStateResolver,
    NpcInnerState,
    relationship_behavior,
)
from .db import DEFAULT_WORLD_ID, GameDatabase
from .domain import QuestState
from .living_conversation import (
    ConversationMemory,
    ConversationMemoryCandidate,
    ConversationThreadState,
    LivingConversationStore,
)
from .npc_profiles import get_npc_profile
from .quest import QUEST_TYPE, QuestService

OFFER_PROPOSAL = f"offer_quest:{QUEST_TYPE}"
_ALLOWED_PROPOSALS = {OFFER_PROPOSAL}
REMEMBER_MIRA_WOOD_COMMITMENT = "remember_commitment:bring_useful_wood_to_mira"
_ALLOWED_SOCIAL_ACTIONS = {REMEMBER_MIRA_WOOD_COMMITMENT}
_ALLOWED_CONVERSATION_ACTS = {
    "answer",
    "ask",
    "challenge",
    "refuse",
    "tease",
    "observe",
    "recall",
    "redirect",
}
_ALLOWED_CONVERSATION_MEMORY_TYPES = {
    "player_claim",
    "preference",
    "commitment",
    "significant_interaction",
}
_MEMORY_IMPORTANCE = {
    "player_claim": 60,
    "preference": 50,
    "commitment": 80,
    "significant_interaction": 70,
}
MIRA_COMMITMENT_FACT = "The player promised Mira to bring useful wood while her workshop was blocked."


def player_mira_commitment_fact_key(player_id: str) -> str:
    return f"player_promised_mira_useful_wood:{player_id}"


@dataclass(frozen=True, slots=True)
class DialogueDecision:
    text: str
    proposal: str | None = None
    used_fallback: bool = False
    social_action: str | None = None
    npc_id: str = "npc_oren"
    conversation_act: str | None = None
    memory_candidates: tuple[ConversationMemoryCandidate, ...] = ()
    open_thread: str | None = None
    resolve_thread: str | None = None


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
    values: tuple[str, ...]
    temperament: str
    humor_style: str
    likes: tuple[str, ...]
    dislikes: tuple[str, ...]
    conversation_preferences: tuple[str, ...]
    avoided_topics: tuple[str, ...]
    warmth_signals: tuple[str, ...]
    conflict_behavior: str
    characteristic_phrases: tuple[str, ...]
    forbidden_phrases: tuple[str, ...]
    default_reply_length: str
    inner_state: NpcInnerState
    relationship_behavior: str
    conversation_memories: tuple[ConversationMemory, ...]
    thread_state: ConversationThreadState
    initiative: ConversationInitiative | None
    activity: str
    location_id: str
    trust: int
    relation: dict[str, int]
    quest: QuestState | None
    memories: tuple[str, ...]
    known_facts: tuple[str, ...]
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
        known_facts = " | ".join(self.known_facts) or "none"
        events = " | ".join(self.own_events) or "none"
        nearby_actors = ", ".join(self.nearby_actors) or "none"
        nearby_entities = ", ".join(self.nearby_entities) or "none"
        conversation_memories = " | ".join(
            f"{item.memory_type}/{item.source_kind}: {item.content}"
            for item in self.conversation_memories
        ) or "none"
        open_threads = " | ".join(self.thread_state.open_threads) or "none"
        initiative_kind = "none" if self.initiative is None else self.initiative.kind
        initiative_cue = "none" if self.initiative is None else self.initiative.cue
        lines = [
            f"npc_id: {self.npc_id}",
            f"npc_name: {self.display_name}",
            f"role: {self.role}",
            f"personality: {self.personality}",
            f"speech_style: {self.speech_style}",
            f"motivations: {' | '.join(self.motivations)}",
            f"knowledge_boundaries: {' | '.join(self.knowledge_boundaries)}",
            f"values: {' | '.join(self.values)}",
            f"temperament: {self.temperament}",
            f"humor_style: {self.humor_style}",
            f"likes: {' | '.join(self.likes)}",
            f"dislikes: {' | '.join(self.dislikes)}",
            f"conversation_preferences: {' | '.join(self.conversation_preferences)}",
            f"avoided_topics: {' | '.join(self.avoided_topics)}",
            f"warmth_signals: {' | '.join(self.warmth_signals)}",
            f"conflict_behavior: {self.conflict_behavior}",
            f"characteristic_phrases: {' | '.join(self.characteristic_phrases)}",
            f"forbidden_phrases: {' | '.join(self.forbidden_phrases)}",
            f"default_reply_length: {self.default_reply_length}",
            f"current_mood: {self.inner_state.mood}",
            f"secondary_mood: {self.inner_state.secondary_mood}",
            f"current_concern: {self.inner_state.current_concern}",
            f"current_desire: {self.inner_state.current_desire}",
            f"conversation_availability: {self.inner_state.availability}",
            f"subjective_stance: {self.inner_state.stance}",
            f"relationship_behavior: {self.relationship_behavior}",
            f"conversation_memories: {conversation_memories}",
            f"open_threads: {open_threads}",
            f"pending_question: {self.thread_state.pending_question or 'none'}",
            f"turn_count_with_player: {self.thread_state.turn_count}",
            f"initiative_kind: {initiative_kind}",
            f"initiative_cue: {initiative_cue}",
            f"activity: {self.activity}",
            f"location: {self.location_id}",
            f"runtime_state: {json.dumps(self.runtime_state, ensure_ascii=False, sort_keys=True)}",
            f"relation_to_player: {json.dumps(self.relation, ensure_ascii=False, sort_keys=True)}",
            f"relevant_memories: {memories}",
            f"known_facts: {known_facts}",
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
                "knowledge_rule: You know only the supplied NPC knowledge and pair-scoped memories. Missing facts are unknown to you.",
                "subjectivity_rule: Treat subjective_stance as your opinion, not as an objective world fact.",
                "initiative_rule: initiative_cue is permission to lead naturally, not an instruction to invent new facts.",
                "memory_rule: A proposed conversation memory records what the player said or what this conversation established; never convert a claim into objective world truth.",
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
        self.conversation_store = LivingConversationStore()
        self.conversation_state_resolver = NpcConversationStateResolver()
        with self.db.connect() as conn:
            self.conversation_store.ensure_schema(conn)

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
                conversation_act = getattr(raw, "conversation_act", None)
                memory_candidates = tuple(getattr(raw, "memory_candidates", ()) or ())
                open_thread = _normalized_optional_text(getattr(raw, "open_thread", None))
                resolve_thread = _normalized_optional_text(getattr(raw, "resolve_thread", None))
                invalid_metadata = not _valid_conversation_metadata(
                    conversation_act=conversation_act,
                    memory_candidates=memory_candidates,
                    open_thread=open_thread,
                    resolve_thread=resolve_thread,
                )
                if not text:
                    decision = _fallback(context)
                elif invalid_metadata:
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
                        conversation_act=conversation_act,
                        memory_candidates=memory_candidates,
                        open_thread=open_thread,
                        resolve_thread=resolve_thread,
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
            tick_row = conn.execute(
                "SELECT tick FROM world_runtime WHERE world_id = ?",
                (DEFAULT_WORLD_ID,),
            ).fetchone()
            if tick_row is None:
                raise RuntimeError(f"missing world runtime for {DEFAULT_WORLD_ID}")
            current_tick = int(tick_row[0])

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
                    conn.execute(
                        "INSERT INTO npc_knowledge "
                        "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
                        "source_kind, source_actor_id, source_world_event_id, source_knowledge_id, "
                        "confidence, shareable, learned_tick, created_at) "
                        "VALUES (?, 'npc_mira', ?, ?, ?, 'player_dialogue', ?, NULL, NULL, "
                        "100, 1, ?, ?) "
                        "ON CONFLICT(knower_actor_id, fact_key) DO NOTHING",
                        (
                            DEFAULT_WORLD_ID,
                            context.player_id,
                            player_mira_commitment_fact_key(context.player_id),
                            MIRA_COMMITMENT_FACT,
                            context.player_id,
                            current_tick,
                            now,
                        ),
                    )

            player_id = context.player_id
            for candidate in resolved.memory_candidates:
                self.conversation_store.add_memory(
                    conn,
                    world_id=DEFAULT_WORLD_ID,
                    npc_actor_id=context.npc_id,
                    player_actor_id=player_id,
                    memory_type=candidate.memory_type,
                    content=candidate.content,
                    source_kind="player_said",
                    importance=_MEMORY_IMPORTANCE[candidate.memory_type],
                    created_tick=current_tick,
                )

            pending_question = (
                resolved.text if resolved.conversation_act == "ask" else None
            )
            last_topic = (
                resolved.open_thread
                or resolved.resolve_thread
                or context.thread_state.last_topic
            )
            self.conversation_store.note_turn(
                conn,
                npc_actor_id=context.npc_id,
                player_actor_id=player_id,
                last_topic=last_topic,
                tick=current_tick,
                pending_question=pending_question,
            )
            if resolved.resolve_thread is not None:
                self.conversation_store.resolve_thread(
                    conn,
                    npc_actor_id=context.npc_id,
                    player_actor_id=player_id,
                    thread=resolved.resolve_thread,
                    tick=current_tick,
                )
            if resolved.open_thread is not None:
                self.conversation_store.open_thread(
                    conn,
                    npc_actor_id=context.npc_id,
                    player_actor_id=player_id,
                    thread=resolved.open_thread,
                    tick=current_tick,
                )

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
                        {
                            "proposal": resolved.proposal,
                            "social_action": resolved.social_action,
                            "conversation_act": resolved.conversation_act,
                            "memory_candidates": [
                                {
                                    "memory_type": candidate.memory_type,
                                    "content": candidate.content,
                                }
                                for candidate in resolved.memory_candidates
                            ],
                            "open_thread": resolved.open_thread,
                            "resolve_thread": resolved.resolve_thread,
                        },
                        ensure_ascii=False,
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
                conversation_act=resolved.conversation_act,
                memory_candidates=resolved.memory_candidates,
                open_thread=resolved.open_thread,
                resolve_thread=resolved.resolve_thread,
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
            knowledge_rows = conn.execute(
                "SELECT fact_text, source_kind, source_actor_id, confidence "
                "FROM npc_knowledge WHERE knower_actor_id = ? "
                "ORDER BY confidence DESC, learned_tick DESC, id DESC LIMIT 8",
                (npc_id,),
            ).fetchall()
            known_facts = tuple(_format_known_fact(row) for row in knowledge_rows)
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

            conversation_memories = self.conversation_store.list_memories(
                conn, npc_id, player_id
            )
            thread_state = self.conversation_store.get_thread_state(
                conn, npc_id, player_id
            )
            inner_state = self.conversation_state_resolver.resolve(
                npc_id=npc_id,
                runtime_state=runtime_state,
                activity=str(npc[1]),
                relation=relation,
                known_facts=known_facts,
            )
            relationship_mode = relationship_behavior(relation)

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
            initiative = resolve_initiative(
                npc_id=npc_id,
                thread_state=thread_state,
                inner_state=inner_state,
                runtime_state=runtime_state,
                known_facts=known_facts,
                own_events=own_events,
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
            values=profile.values,
            temperament=profile.temperament,
            humor_style=profile.humor_style,
            likes=profile.likes,
            dislikes=profile.dislikes,
            conversation_preferences=profile.conversation_preferences,
            avoided_topics=profile.avoided_topics,
            warmth_signals=profile.warmth_signals,
            conflict_behavior=profile.conflict_behavior,
            characteristic_phrases=profile.characteristic_phrases,
            forbidden_phrases=profile.forbidden_phrases,
            default_reply_length=profile.default_reply_length,
            inner_state=inner_state,
            relationship_behavior=relationship_mode,
            conversation_memories=conversation_memories,
            thread_state=thread_state,
            initiative=initiative,
            activity=str(npc[1]),
            location_id=npc_location,
            trust=relation["trust"],
            relation=relation,
            quest=quest_state,
            memories=memories,
            known_facts=known_facts,
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

            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                timeout=8.0,
                max_retries=1,
            )
        self.client = client
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5")

    def generate(self, context: DialogueContext) -> DialogueDecision:
        display_name = getattr(context, "display_name", "Орен")
        npc_id = getattr(context, "npc_id", "npc_oren")
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                f"You are {display_name}, a grounded NPC in a small remote fantasy village. "
                "Speak naturally and briefly in Russian, following the supplied personality, voice bible and current state. "
                "Use only the supplied world state and knowledge. Never invent inventory, rewards, completed actions, "
                "locations, private conversations or world facts. Stay a person in the world, not a helpful assistant. "
                "Never say generic assistant phrases such as 'интересный вопрос' or 'чем я могу помочь'. "
                "Do not always agree. Do not end every reply with a question. Do not use bullet lists in ordinary speech. "
                "Do not restate the player's question, explain your own personality, or force a helpful answer when refusal, "
                "silence, a counter-question, dry humor or a topic change better fits the supplied character and situation. "
                "Use current_mood, subjective_stance, relationship_behavior and initiative_cue to decide how to speak, but "
                "never turn those labels into explicit system language in the reply. "
                "For conversation_act choose the social shape of the reply. Propose at most two durable memory_candidates only "
                "for useful player claims, preferences, commitments or significant interactions. A player claim remains a claim, "
                "never objective world truth. Use open_thread only for a genuinely unfinished topic or question and resolve_thread "
                "only when an existing thread was actually answered or closed. "
                "The proposal field may only offer the existing bring_5_firewood quest when you are Oren and the supplied "
                "state permits it; otherwise use none."
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
                            "conversation_act": {
                                "type": "string",
                                "enum": sorted(_ALLOWED_CONVERSATION_ACTS) + ["none"],
                            },
                            "memory_candidates": {
                                "type": "array",
                                "maxItems": 2,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "memory_type": {
                                            "type": "string",
                                            "enum": sorted(_ALLOWED_CONVERSATION_MEMORY_TYPES),
                                        },
                                        "content": {"type": "string", "maxLength": 240},
                                    },
                                    "required": ["memory_type", "content"],
                                    "additionalProperties": False,
                                },
                            },
                            "open_thread": {"type": "string", "maxLength": 180},
                            "resolve_thread": {"type": "string", "maxLength": 180},
                        },
                        "required": [
                            "text",
                            "proposal",
                            "social_action",
                            "conversation_act",
                            "memory_candidates",
                            "open_thread",
                            "resolve_thread",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
        )
        payload = json.loads(response.output_text)
        proposal = payload.get("proposal", "none")
        if proposal == "none":
            proposal = None
        elif proposal not in _ALLOWED_PROPOSALS:
            raise ValueError(f"invalid dialogue proposal: {proposal}")
        social_action = payload.get("social_action", "none")
        if social_action == "none":
            social_action = None
        elif social_action not in _ALLOWED_SOCIAL_ACTIONS:
            raise ValueError(f"invalid dialogue social action: {social_action}")
        conversation_act = payload.get("conversation_act", "none")
        if conversation_act == "none":
            conversation_act = None
        elif conversation_act not in _ALLOWED_CONVERSATION_ACTS:
            raise ValueError(f"invalid conversation act: {conversation_act}")
        memory_candidates = tuple(
            ConversationMemoryCandidate(
                memory_type=str(item.get("memory_type", "")),
                content=str(item.get("content", "")),
            )
            for item in payload.get("memory_candidates", [])
            if isinstance(item, dict)
        )
        open_thread = _normalized_optional_text(payload.get("open_thread"))
        resolve_thread = _normalized_optional_text(payload.get("resolve_thread"))
        if not _valid_conversation_metadata(
            conversation_act=conversation_act,
            memory_candidates=memory_candidates,
            open_thread=open_thread,
            resolve_thread=resolve_thread,
        ):
            raise ValueError("invalid living conversation metadata")
        return DialogueDecision(
            text=str(payload["text"]),
            proposal=proposal,
            social_action=social_action,
            npc_id=npc_id,
            conversation_act=conversation_act,
            memory_candidates=memory_candidates,
            open_thread=open_thread,
            resolve_thread=resolve_thread,
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
        if _asks_about_social_knowledge(context.user_text) and _has_mira_commitment_report(context):
            return DialogueDecision(
                text="Каспар пожимает плечом: «Мира говорила, что ты обещал помочь ей с древесиной.»",
                used_fallback=True,
                npc_id=context.npc_id,
            )
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
    if context.npc_id == "npc_wayfarer_1":
        if _asks_about_wayfarer_news(context.user_text) and _has_wayfarer_road_fact(context):
            return DialogueDecision(
                text="Тален отвечает: «Сильные дожди размыли часть восточной дороги. Следующий торговый караван задержится.»",
                used_fallback=True,
                npc_id=context.npc_id,
            )
        return DialogueDecision(
            text="Тален коротко кивает: «С дороги я ещё не отошёл. Спроси о пути — расскажу, что знаю точно.»",
            used_fallback=True,
            npc_id=context.npc_id,
        )
    if context.npc_id == "npc_oren":
        if _asks_about_wayfarer_news(context.user_text) and _has_talen_road_report(context):
            return DialogueDecision(
                text="Орен отвечает: «Тален сказал, что сильные дожди размыли часть восточной дороги. Следующий торговый караван задержится.»",
                used_fallback=True,
                npc_id=context.npc_id,
            )
        if _asks_about_hospitality(context.user_text):
            if bool(context.runtime_state.get("bread_received")):
                return DialogueDecision(
                    text="Орен кивает: «Спасибо. Хлеб как раз пригодился гостю после дороги.»",
                    used_fallback=True,
                    npc_id=context.npc_id,
                )
            if bool(context.runtime_state.get("bread_requested")):
                return DialogueDecision(
                    text="Орен кивает в сторону гостя: «Если хочешь помочь — принеси хлеб с площади для Талена.»",
                    used_fallback=True,
                    npc_id=context.npc_id,
                )

    state = context.quest
    if state is None:
        return DialogueDecision(
            text=f"{context.display_name} молча кивает.",
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


def _valid_conversation_metadata(
    *,
    conversation_act: object,
    memory_candidates: tuple[object, ...],
    open_thread: str | None,
    resolve_thread: str | None,
) -> bool:
    if conversation_act is not None and conversation_act not in _ALLOWED_CONVERSATION_ACTS:
        return False
    if len(memory_candidates) > 2:
        return False
    for candidate in memory_candidates:
        if not isinstance(candidate, ConversationMemoryCandidate):
            return False
        if candidate.memory_type not in _ALLOWED_CONVERSATION_MEMORY_TYPES:
            return False
        if not candidate.content.strip() or len(candidate.content.strip()) > 240:
            return False
    for thread in (open_thread, resolve_thread):
        if thread is not None and (not thread.strip() or len(thread) > 180):
            return False
    return True


def _normalized_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "none":
        return None
    return text


def _format_known_fact(row) -> str:
    source_actor = row["source_actor_id"]
    source = "unknown" if source_actor is None else str(source_actor)
    return (
        f"source={source} kind={row['source_kind']}: {row['fact_text']} "
        f"[confidence={int(row['confidence'])}]"
    )


def _has_mira_commitment_report(context: DialogueContext) -> bool:
    return any(
        "source=npc_mira" in fact
        and "mira said the player promised to bring useful wood" in fact.lower()
        for fact in context.known_facts
    )


def _has_wayfarer_road_fact(context: DialogueContext) -> bool:
    return any(
        "source=npc_wayfarer_1" in fact
        and "kind=direct_event" in fact
        and "heavy rain washed out part of the eastern road" in fact.lower()
        and "merchant caravan will be delayed" in fact.lower()
        for fact in context.known_facts
    )


def _has_talen_road_report(context: DialogueContext) -> bool:
    return any(
        "source=npc_wayfarer_1" in fact
        and "kind=npc_report" in fact
        and "heavy rain washed out part of the eastern road" in fact.lower()
        and "merchant caravan will be delayed" in fact.lower()
        for fact in context.known_facts
    )


def _asks_about_wayfarer_news(user_text: str) -> bool:
    text = user_text.lower()
    return any(
        token in text
        for token in ("тален", "путник", "дорог", "караван", "новост", "рассказ")
    )


def _asks_about_hospitality(user_text: str) -> bool:
    text = user_text.lower()
    return any(token in text for token in ("хлеб", "гост", "помощ"))


def _asks_about_social_knowledge(user_text: str) -> bool:
    text = user_text.lower()
    return any(token in text for token in ("слыш", "обо мне", "обещ", "мира"))


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