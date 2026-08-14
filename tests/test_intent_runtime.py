import importlib

import pytest


def test_runtime_disables_semantic_provider_without_explicit_model(tmp_path):
    module = importlib.import_module("samseberpg.discord_bot")
    config = module.load_runtime_config(
        {
            "DISCORD_BOT_TOKEN": "secret-token",
            "SAM_SEBE_DB": str(tmp_path / "world.db"),
        }
    )
    assert config.ollama_model is None
    assert config.ollama_url == "http://127.0.0.1:11434"
    assert config.ollama_timeout_seconds == 5.0
    app = module._build_application(config)
    assert app.intent_resolver is None


def test_runtime_enables_configured_ollama_semantic_provider(tmp_path):
    module = importlib.import_module("samseberpg.discord_bot")
    from samseberpg.ollama_intent import OllamaIntentResolver

    config = module.load_runtime_config(
        {
            "DISCORD_BOT_TOKEN": "secret-token",
            "SAM_SEBE_DB": str(tmp_path / "world.db"),
            "OLLAMA_MODEL": "qwen3:4b",
            "OLLAMA_URL": "http://localhost:9999/",
            "OLLAMA_TIMEOUT_SECONDS": "3.5",
        }
    )
    app = module._build_application(config)
    assert isinstance(app.intent_resolver, OllamaIntentResolver)
    assert app.intent_resolver.model == "qwen3:4b"
    assert app.intent_resolver.base_url == "http://localhost:9999"
    assert app.intent_resolver.timeout == 3.5


def test_runtime_rejects_invalid_ollama_timeout():
    module = importlib.import_module("samseberpg.discord_bot")
    with pytest.raises(RuntimeError, match="OLLAMA_TIMEOUT_SECONDS"):
        module.load_runtime_config(
            {"DISCORD_BOT_TOKEN": "secret", "OLLAMA_TIMEOUT_SECONDS": "zero"}
        )
    with pytest.raises(RuntimeError, match="OLLAMA_TIMEOUT_SECONDS"):
        module.load_runtime_config(
            {"DISCORD_BOT_TOKEN": "secret", "OLLAMA_TIMEOUT_SECONDS": "0"}
        )
