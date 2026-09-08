from __future__ import annotations

from types import SimpleNamespace

from samseberpg.dialogue import OpenAIResponsesProvider
from samseberpg.npc_profiles import get_npc_profile


VOICE_FIELDS = (
    "values",
    "temperament",
    "humor_style",
    "likes",
    "dislikes",
    "conversation_preferences",
    "avoided_topics",
    "warmth_signals",
    "conflict_behavior",
    "characteristic_phrases",
    "forbidden_phrases",
    "default_reply_length",
)


def test_stream_npc_profiles_have_complete_distinct_voice_bibles() -> None:
    profiles = [
        get_npc_profile("npc_oren"),
        get_npc_profile("npc_mira"),
        get_npc_profile("npc_kaspar"),
        get_npc_profile("npc_wayfarer_1"),
    ]

    for profile in profiles:
        for field in VOICE_FIELDS:
            value = getattr(profile, field)
            assert value

    assert len({profile.temperament for profile in profiles}) == 4
    assert len({profile.humor_style for profile in profiles}) == 4
    assert len({tuple(profile.characteristic_phrases) for profile in profiles}) == 4
    assert all("интересный вопрос" in " ".join(profile.forbidden_phrases).lower() for profile in profiles)


def test_openai_provider_instructs_npc_to_avoid_assistant_voice() -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text=(
                    '{"text":"Ладно.","proposal":"none",'
                    '"social_action":"none"}'
                )
            )

    provider = OpenAIResponsesProvider(
        client=SimpleNamespace(responses=FakeResponses()),
        model="gpt-5",
    )
    context = SimpleNamespace(
        npc_id="npc_kaspar",
        display_name="Каспар",
        to_prompt=lambda: "STATE\nplayer_says: Привет",
    )

    provider.generate(context)

    instructions = str(captured["instructions"]).lower()
    assert "интересный вопрос" in instructions
    assert "чем я могу помочь" in instructions
    assert "do not always agree" in instructions
    assert "do not end every reply with a question" in instructions
    assert "do not use bullet lists" in instructions
