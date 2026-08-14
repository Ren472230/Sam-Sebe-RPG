import importlib
from pathlib import Path

import pytest


def test_discord_runtime_config_requires_token_and_parses_values():
    module = importlib.import_module("samseberpg.discord_bot")

    with pytest.raises(RuntimeError, match="DISCORD_BOT_TOKEN"):
        module.load_runtime_config({})

    config = module.load_runtime_config(
        {
            "DISCORD_BOT_TOKEN": "secret-token",
            "DISCORD_GUILD_ID": "123456789",
            "SAM_SEBE_DB": "/tmp/world.db",
        }
    )
    assert config.token == "secret-token"
    assert config.guild_id == 123456789
    assert str(config.db_path) == "/tmp/world.db"


def test_importing_discord_runtime_does_not_require_optional_discord_package():
    module = importlib.import_module("samseberpg.discord_bot")
    assert callable(module.run)


def test_only_discord_runtime_module_mentions_discord_imports():
    package = Path("src/samseberpg")
    offenders = []
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "import discord" in text or "from discord" in text:
            offenders.append(path.name)
    assert offenders == ["discord_bot.py"]


def test_pyproject_declares_discord_as_optional_extra():
    import tomllib

    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["optional-dependencies"]["discord"] == ["discord.py>=2.7,<3"]
