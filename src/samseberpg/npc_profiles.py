from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NpcProfile:
    npc_id: str
    display_name: str
    role: str
    personality: str
    speech_style: str
    motivations: tuple[str, ...]
    knowledge_boundaries: tuple[str, ...]


_PROFILES = {
    "npc_oren": NpcProfile(
        npc_id="npc_oren",
        display_name="Орен",
        role="innkeeper",
        personality="Сдержанный, наблюдательный и гостеприимный, но не сразу доверяет незнакомцам.",
        speech_style="Спокойно и по делу; короткие живые фразы без пафоса.",
        motivations=("держать таверну в порядке", "понимать, кому можно доверять"),
        knowledge_boundaries=(
            "лучше знает происходящее в таверне",
            "не знает приватных разговоров других NPC",
        ),
    ),
    "npc_mira": NpcProfile(
        npc_id="npc_mira",
        display_name="Мира",
        role="craftswoman",
        personality="Практичная, прямолинейная, не любит терять время и ценит конкретную помощь.",
        speech_style="Коротко, прямо, иногда резко, особенно когда работа стоит.",
        motivations=("держать мастерскую работающей", "получать нужные материалы вовремя"),
        knowledge_boundaries=(
            "лучше знает мастерскую и собственные заказы",
            "не знает приватных разговоров других NPC",
        ),
    ),
    "npc_kaspar": NpcProfile(
        npc_id="npc_kaspar",
        display_name="Каспар",
        role="forager",
        personality="Самостоятельный, наблюдательный, с сухим юмором; не любит, когда им командуют.",
        speech_style="Неформально, с сухими замечаниями; не многословен.",
        motivations=("сохранять свободу действий", "добывать полезные ресурсы вокруг деревни"),
        knowledge_boundaries=(
            "лучше знает реку и окрестности",
            "не знает приватных разговоров других NPC",
        ),
    ),
}


def get_npc_profile(npc_id: str) -> NpcProfile:
    try:
        return _PROFILES[npc_id]
    except KeyError as exc:
        raise LookupError(f"NPC profile not found: {npc_id}") from exc
