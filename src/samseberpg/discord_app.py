from __future__ import annotations

from .dialogue import DialogueService
from .digest import WorldDigestService
from .domain import ActionType
from .game import GameService
from .intent import (
    IntentResolutionError,
    IntentResolver,
    build_intent_context,
    canonicalize_proposal,
)
from .parser import parse_action
from .presentation import (
    HELP_TEXT,
    limit_message,
    render_action_result,
    render_me,
    render_world,
    render_world_digest,
)


class DiscordGameApplication:
    def __init__(self, game: GameService, intent_resolver: IntentResolver | None = None):
        self.game = game
        self.intent_resolver = intent_resolver

    def handle_look(self, discord_user_id: str, display_name: str) -> str:
        player_id = self.game.register_player(discord_user_id, display_name)
        return render_world(self.game.observe(player_id))

    def handle_me(self, discord_user_id: str, display_name: str) -> str:
        player_id = self.game.register_player(discord_user_id, display_name)
        return render_me(self.game.observe(player_id))

    def handle_news(self, discord_user_id: str, display_name: str) -> str:
        player_id = self.game.register_player(discord_user_id, display_name)
        return render_world_digest(WorldDigestService(self.game).build(player_id))

    def handle_act(
        self,
        discord_user_id: str,
        display_name: str,
        text: str,
        interaction_id: str,
    ) -> str:
        player_id = self.game.register_player(discord_user_id, display_name)
        action = parse_action(text, player_id)
        if action is None and self.intent_resolver is not None:
            context = build_intent_context(self.game.observe(player_id))
            try:
                proposal = self.intent_resolver.resolve(text, context)
            except IntentResolutionError:
                return f"Не удалось безопасно разобрать действие.\n\n{HELP_TEXT}"
            action = canonicalize_proposal(proposal, context, source_text=text)
            if action is None:
                return f"Не понял действие или оно пока не поддерживается.\n\n{HELP_TEXT}"
        if action is None:
            return HELP_TEXT

        result = self.game.execute(action, external_id=interaction_id)
        if result.success and action.action_type == ActionType.LOOK:
            return render_world(self.game.observe(player_id))
        if result.success and action.action_type == ActionType.TALK:
            dialogue = DialogueService(self.game).render(player_id, result)
            return limit_message(
                f"{render_action_result(result)}\n\n{dialogue}\n\n{render_world(self.game.observe(player_id))}"
            )
        if result.success:
            return limit_message(
                f"{render_action_result(result)}\n\n{render_world(self.game.observe(player_id))}"
            )
        return render_action_result(result)
