from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.game import GameService
from samseberpg.intent import IntentProposal


class TalkDemoResolver:
    def resolve(self, text, context):
        if text == "спрошу Миру, как дела":
            return IntentProposal("TALK", None, "npc_mira", None, "visible Mira")
        if text == "крикну Орену отсюда":
            return IntentProposal("TALK", None, "npc_oren", None, "hidden Oren")
        return IntentProposal("UNSUPPORTED", None, None, None, "unsupported")


def main() -> None:
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="sam-sebe-talk-") as temp_dir:
        path = Path(temp_dir) / "game.db"
        db = GameDatabase(path)
        db.initialize()
        db.bootstrap_if_empty(now)
        game = GameService(db, FakeClock(now))
        app = DiscordGameApplication(game, intent_resolver=TalkDemoResolver())

        first = app.handle_act("demo-talk", "Ren", "сказать npc_mira привет", "talk-explicit-1")
        replay = app.handle_act("demo-talk", "Ren", "сказать npc_mira привет", "talk-explicit-1")
        assert first == replay
        with db.connect() as conn:
            player = conn.execute("SELECT actor_id FROM players WHERE discord_user_id='demo-talk'").fetchone()[0]
            familiarity = conn.execute(
                "SELECT familiarity FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
                (player,),
            ).fetchone()[0]
        assert familiarity == 1
        print("[canonical talk] Explicit SAY created one TALK event and familiarity +1; retry did not double-count")

        natural = app.handle_act("demo-talk", "Ren", "спрошу Миру, как дела", "talk-natural-2")
        assert "Мира" in natural
        with db.connect() as conn:
            familiarity = conn.execute(
                "SELECT familiarity FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
                (player,),
            ).fetchone()[0]
        assert familiarity == 2
        print("[semantic talk] Natural phrase resolved to the same canonical TALK action")

        with db.connect() as conn:
            before = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
        rejected = app.handle_act("demo-talk", "Ren", "крикну Орену отсюда", "talk-hidden")
        assert "не понял" in rejected.casefold()
        with db.connect() as conn:
            after = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
        assert after == before
        print("[guardrail] Hidden NPC semantic target was rejected before event creation")

        reopened = GameDatabase(path)
        reopened.initialize()
        GameService(reopened, FakeClock(now)).observe(player)
        with reopened.connect() as conn:
            persisted = conn.execute(
                "SELECT familiarity FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
                (player,),
            ).fetchone()[0]
        assert persisted == 2
        print("[persistence] Mira familiarity remains 2 after restart")
        print("\nNPC TALK demo: PASS")


if __name__ == "__main__":
    main()
