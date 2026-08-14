from samseberpg.ollama_intent import INTENT_JSON_SCHEMA, SYSTEM_PROMPT


def test_ollama_contract_includes_talk():
    assert "TALK" in INTENT_JSON_SCHEMA["properties"]["action_type"]["enum"]
    assert "TALK" in SYSTEM_PROMPT
