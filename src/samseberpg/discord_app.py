from __future__ import annotations

from .domain import ActionType
from .game import GameService
from .parser import parse_action
from .presentation import HELP_TEXT, limit_message, render_action_result, render_me, render_world


class DiscordGameApplication:
    def __init__(self, game: GameService):
        self.game = game

    def handle_look(self, discord_user_id: str, display_name: str) -> str:
        player_id = self.game.register_player(discord_user_id, display_name)
        return render_world(self.game.observe(player_id))

    def handle_me(self, discord_user_id: str, display_name: str) -> str:
        player_id = self.game.register_player(discord_user_id, display_name)
        return render_me(self.game.observe(player_id))

    def handle_act(
        self,
        discord_user_id: str,
        display_name: str,
        text: str,
        interaction_id: str,
    ) -> str:
        player_id = self.game.register_player(discord_user_id, display_name)
        action = parse_action(text, player_id)
        if action is None:
            return HELP_TEXT

        result = self.game.execute(action, external_id=interaction_id)
        if result.success and action.action_type == ActionType.LOOK:
            return render_world(self.game.observe(player_id))
        if result.success:
            return limit_message(
                f"{render_action_result(result)}\n\n{render_world(self.game.observe(player_id))}"
            )
        return render_action_result(result)
