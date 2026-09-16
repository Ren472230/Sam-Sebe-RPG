from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NpcInnerState:
    mood: str
    secondary_mood: str
    current_concern: str
    current_desire: str
    availability: str
    stance: str


class NpcConversationStateResolver:
    def resolve(
        self,
        *,
        npc_id: str,
        runtime_state: dict[str, object],
        activity: str,
        relation: dict[str, int],
        known_facts: tuple[str, ...],
    ) -> NpcInnerState:
        road_delay_known = _has_road_delay(known_facts)

        if npc_id == "npc_mira":
            if bool(runtime_state.get("requested_wood", False)):
                return NpcInnerState(
                    mood="irritated",
                    secondary_mood="worried",
                    current_concern="workshop_stopped",
                    current_desire="obtain_useful_wood",
                    availability="low",
                    stance="work_first",
                )
            return NpcInnerState(
                mood="focused",
                secondary_mood="calm",
                current_concern="keep_workshop_running",
                current_desire="continue_work",
                availability="medium",
                stance="work_first",
            )

        if npc_id == "npc_oren":
            if bool(runtime_state.get("bread_received", False)):
                return NpcInnerState(
                    mood="relieved",
                    secondary_mood="warm",
                    current_concern="guest_cared_for",
                    current_desire="keep_inn_running",
                    availability="medium",
                    stance=(
                        "road_delay_threatens_supplies"
                        if road_delay_known
                        else "hospitality_first"
                    ),
                )
            if bool(runtime_state.get("bread_requested", False)):
                return NpcInnerState(
                    mood="concerned",
                    secondary_mood="hospitable",
                    current_concern="guest_and_supplies",
                    current_desire="care_for_guest",
                    availability="medium",
                    stance=(
                        "road_delay_threatens_supplies"
                        if road_delay_known
                        else "hospitality_first"
                    ),
                )
            if road_delay_known:
                return NpcInnerState(
                    mood="concerned",
                    secondary_mood="measured",
                    current_concern="tavern_supplies",
                    current_desire="prepare_for_delay",
                    availability="medium",
                    stance="road_delay_threatens_supplies",
                )
            return NpcInnerState(
                mood="measured",
                secondary_mood="hospitable",
                current_concern="keep_inn_orderly",
                current_desire="read_the_room",
                availability="medium",
                stance="hospitality_first",
            )

        if npc_id == "npc_kaspar":
            carrying = runtime_state.get("carrying_wood", 0)
            has_active_goal = bool(runtime_state.get("goal")) or (
                isinstance(carrying, int) and not isinstance(carrying, bool) and carrying > 0
            )
            if has_active_goal:
                return NpcInnerState(
                    mood="focused",
                    secondary_mood="skeptical",
                    current_concern="useful_wood",
                    current_desire="solve_it_himself",
                    availability="low",
                    stance="independence_over_promises",
                )
            return NpcInnerState(
                mood="observant",
                secondary_mood="dry",
                current_concern="river_and_resources",
                current_desire="keep_independence",
                availability="medium",
                stance="independence_over_promises",
            )

        if npc_id == "npc_wayfarer_1":
            if bool(runtime_state.get("arrived", False)):
                return NpcInnerState(
                    mood="tired",
                    secondary_mood="wary",
                    current_concern="recover_from_road",
                    current_desire="rest_and_share_reliable_news",
                    availability="low",
                    stance="trust_what_i_saw" if road_delay_known else "speak_only_from_experience",
                )
            return NpcInnerState(
                mood="tired",
                secondary_mood="guarded",
                current_concern="keep_moving",
                current_desire="reach_shelter",
                availability="low",
                stance="speak_only_from_experience",
            )

        return NpcInnerState(
            mood="calm",
            secondary_mood="neutral",
            current_concern="current_activity",
            current_desire="continue_current_activity",
            availability="medium",
            stance="grounded",
        )


def relationship_behavior(relation: dict[str, int]) -> str:
    familiarity = int(relation.get("familiarity", 0))
    trust = int(relation.get("trust", 0))
    affinity = int(relation.get("affinity", 0))
    fear = int(relation.get("fear", 0))
    conflict = int(relation.get("conflict", 0))

    if conflict >= 50 or (conflict >= 35 and trust <= -10):
        return "hostile"
    if conflict >= 25 or fear >= 25 or trust <= -15 or affinity <= -20:
        return "distrustful"
    if trust >= 30 and affinity >= 25 and familiarity >= 20:
        return "warm"
    if familiarity >= 15 and trust >= 10 and affinity >= 5:
        return "comfortable"
    if familiarity > 0 or trust > 0 or affinity > 0:
        return "neutral"
    return "guarded"


def _has_road_delay(known_facts: tuple[str, ...]) -> bool:
    for fact in known_facts:
        lowered = fact.lower()
        if (
            "heavy rain washed out part of the eastern road" in lowered
            and "merchant caravan will be delayed" in lowered
        ):
            return True
    return False
