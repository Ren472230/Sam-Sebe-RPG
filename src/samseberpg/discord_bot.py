from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .clock import SystemClock
from .db import GameDatabase
from .discord_app import DiscordGameApplication
from .game import GameService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    token: str
    db_path: Path
    guild_id: int | None = None


def load_runtime_config(env: Mapping[str, str] | None = None) -> RuntimeConfig:
    values = os.environ if env is None else env
    token = values.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required")

    guild_raw = values.get("DISCORD_GUILD_ID", "").strip()
    guild_id: int | None = None
    if guild_raw:
        try:
            guild_id = int(guild_raw)
        except ValueError as exc:
            raise RuntimeError("DISCORD_GUILD_ID must be an integer") from exc

    db_path = Path(values.get("SAM_SEBE_DB", "game.db")).expanduser()
    return RuntimeConfig(token=token, db_path=db_path, guild_id=guild_id)


def _build_application(config: RuntimeConfig) -> DiscordGameApplication:
    clock = SystemClock()
    db = GameDatabase(config.db_path)
    db.initialize()
    db.bootstrap_if_empty(clock.now())
    return DiscordGameApplication(GameService(db, clock))


def run() -> None:
    config = load_runtime_config()
    try:
        import discord
        from discord.ext import commands
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Discord support is not installed. Run: pip install -e '.[discord]'"
        ) from exc

    logging.basicConfig(level=logging.INFO)
    application = _build_application(config)

    class LivingWorldBot(commands.Bot):
        async def setup_hook(self) -> None:
            if config.guild_id is not None:
                guild = discord.Object(id=config.guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info("Synced %s commands to guild %s", len(synced), config.guild_id)
            else:
                synced = await self.tree.sync()
                logger.info("Synced %s global commands", len(synced))

    bot = LivingWorldBot(
        command_prefix=commands.when_mentioned,
        intents=discord.Intents.none(),
        description="Sam-Sebe-RPG Living World MVP",
    )

    def identity(interaction) -> tuple[str, str]:
        user = interaction.user
        display_name = getattr(user, "display_name", None) or getattr(user, "name", "Player")
        return str(user.id), str(display_name)

    async def guild_only_guard(interaction) -> bool:
        if interaction.guild_id is not None:
            return True
        await interaction.response.send_message(
            "Эта версия живого мира доступна только внутри Discord-сервера.",
            ephemeral=True,
        )
        return False

    @bot.tree.command(name="look", description="Осмотреть текущее место")
    async def look(interaction: discord.Interaction) -> None:
        if not await guild_only_guard(interaction):
            return
        user_id, display_name = identity(interaction)
        text = application.handle_look(user_id, display_name)
        await interaction.response.send_message(text)

    @bot.tree.command(name="me", description="Показать персонажа и инвентарь")
    async def me(interaction: discord.Interaction) -> None:
        if not await guild_only_guard(interaction):
            return
        user_id, display_name = identity(interaction)
        text = application.handle_me(user_id, display_name)
        await interaction.response.send_message(text, ephemeral=True)

    @bot.tree.command(name="act", description="Совершить действие в мире")
    async def act(interaction: discord.Interaction, text: str) -> None:
        if not await guild_only_guard(interaction):
            return
        user_id, display_name = identity(interaction)
        response = application.handle_act(
            user_id,
            display_name,
            text,
            str(interaction.id),
        )
        await interaction.response.send_message(response)

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error) -> None:
        logger.error(
            "Unhandled Discord application command error",
            exc_info=(type(error), error, error.__traceback__),
        )
        message = "Не удалось обработать команду. Состояние мира не изменено повторно."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    bot.run(config.token)


if __name__ == "__main__":
    run()
