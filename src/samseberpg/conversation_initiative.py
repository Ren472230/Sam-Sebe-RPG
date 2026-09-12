from __future__ import annotations

from dataclasses import dataclass

from .conversation_state import NpcInnerState
from .living_conversation import ConversationThreadState


@dataclass(frozen=True, slots=True)
class ConversationInitiative:
    kind: str
    cue: str


def resolve_initiative(
    *,
    npc_id: str,
    thread_state: ConversationThreadState,
    inner_state: NpcInnerState,
    runtime_state: dict[str, object],
    known_facts: tuple[str, ...],
    own_events: tuple[str, ...],
) -> ConversationInitiative | None:
    if thread_state.pending_question:
        return ConversationInitiative(
            kind="unfinished_thread",
            cue=f"Вернись к незавершённому вопросу, если это звучит естественно: {thread_state.pending_question}",
        )

    if npc_id == "npc_mira" and bool(runtime_state.get("requested_wood", False)):
        return ConversationInitiative(
            kind="current_request",
            cue="Работа Миры стоит без пригодной древесины; она может сама поднять эту тему.",
        )

    if (
        npc_id == "npc_oren"
        and bool(runtime_state.get("bread_requested", False))
        and not bool(runtime_state.get("bread_received", False))
    ):
        return ConversationInitiative(
            kind="current_request",
            cue="Орену нужен хлеб для гостя; он может сам упомянуть заботу о госте.",
        )

    if own_events:
        latest = own_events[-1]
        return ConversationInitiative(
            kind="recent_event",
            cue=f"Ты можешь сам коротко отреагировать на своё недавнее действие: {latest}",
        )

    if inner_state.current_concern not in {"current_activity", "keep_inn_orderly", "river_and_resources"}:
        return ConversationInitiative(
            kind="current_concern",
            cue=f"Если уместно, сам затронь текущую заботу: {inner_state.current_concern}.",
        )

    return None
