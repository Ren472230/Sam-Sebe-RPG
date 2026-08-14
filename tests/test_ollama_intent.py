import json
from urllib.error import URLError

import pytest

from samseberpg.domain import VisibleActor, VisibleEntity
from samseberpg.intent import IntentContext, IntentResolutionError
from samseberpg.ollama_intent import INTENT_JSON_SCHEMA, OllamaIntentResolver


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class RecordingOpener:
    def __init__(self, response_payload=None, error=None):
        self.response_payload = response_payload
        self.error = error
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        return FakeResponse(self.response_payload)


def context():
    return IntentContext(
        player_id="player_1",
        coins=10,
        location_id="workshop_yard",
        exits=("village_square",),
        actors=(VisibleActor("npc_mira", "Мира", "npc", "работает"),),
        entities=(VisibleEntity("stone_flat_1", "Плоский камень", "stone", True, {"throwable": True}),),
        inventory=(),
    )


def ollama_response(content):
    return json.dumps(
        {"message": {"role": "assistant", "content": json.dumps(content)}}
    ).encode()


def test_ollama_resolver_posts_structured_nonstreaming_chat_with_canonical_context():
    opener = RecordingOpener(
        ollama_response(
            {
                "action_type": "TAKE",
                "item_id": None,
                "target_id": "stone_flat_1",
                "destination_id": None,
                "reason": "player wants the visible flat stone",
            }
        )
    )
    resolver = OllamaIntentResolver(
        model="qwen3:4b",
        base_url="http://127.0.0.1:11434/",
        timeout=4.5,
        opener=opener,
    )

    proposal = resolver.resolve("подберу плоский камень", context())

    assert proposal.action_type == "TAKE"
    assert proposal.target_id == "stone_flat_1"
    request, timeout = opener.calls[0]
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert timeout == 4.5
    assert request.get_header("Content-type") == "application/json"
    body = json.loads(request.data.decode())
    assert body["model"] == "qwen3:4b"
    assert body["stream"] is False
    assert body["format"] == INTENT_JSON_SCHEMA
    assert body["options"]["temperature"] == 0
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    user_payload = json.loads(body["messages"][1]["content"])
    assert user_payload["player_text"] == "подберу плоский камень"
    assert user_payload["context"]["location_id"] == "workshop_yard"
    assert user_payload["context"]["exits"] == ["village_square"]
    assert user_payload["context"]["visible_entities"][0]["id"] == "stone_flat_1"


@pytest.mark.parametrize(
    "response_payload",
    [
        b"not-json",
        json.dumps({"message": {"content": "not-json"}}).encode(),
        ollama_response({"action_type": "TAKE"}),
        ollama_response(
            {
                "action_type": "DELETE_WORLD",
                "item_id": None,
                "target_id": None,
                "destination_id": None,
                "reason": "bad action",
            }
        ),
        json.dumps({"message": {}}).encode(),
    ],
)
def test_ollama_invalid_responses_raise_typed_resolution_error(response_payload):
    resolver = OllamaIntentResolver(
        model="test-model",
        opener=RecordingOpener(response_payload),
    )
    with pytest.raises(IntentResolutionError):
        resolver.resolve("anything", context())


def test_ollama_transport_failure_becomes_typed_resolution_error():
    resolver = OllamaIntentResolver(
        model="test-model",
        opener=RecordingOpener(error=URLError("connection refused")),
    )
    with pytest.raises(IntentResolutionError, match="Ollama"):
        resolver.resolve("anything", context())


def test_ollama_resolver_rejects_empty_model_and_invalid_timeout():
    with pytest.raises(ValueError):
        OllamaIntentResolver(model="")
    with pytest.raises(ValueError):
        OllamaIntentResolver(model="model", timeout=0)


def test_only_ollama_intent_module_owns_ollama_http_protocol():
    from pathlib import Path

    offenders = []
    for path in Path("src/samseberpg").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "/api/chat" in text or "from urllib.request import" in text:
            offenders.append(path.name)
    assert offenders == ["ollama_intent.py"]
