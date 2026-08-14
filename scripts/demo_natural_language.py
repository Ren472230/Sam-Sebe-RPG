from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.game import GameService
from samseberpg.intent import IntentProposal


class DemoSemanticResolver:
    """Deterministic stand-in that demonstrates the semantic provider contract, not an LLM."""

    def __init__(self):
        self.proposals = {
            "подберу плоский камень": IntentProposal(
                "TAKE", None, "stone_flat_1", None, "visible flat stone"
            ),
            "пойду к таверне": IntentProposal(
                "MOVE", None, None, "village_square", "adjacent square"
            ),
            "швырну камень в вывеску": IntentProposal(
                "THROW", "stone_flat_1", "tavern_sign", None, "visible target"
            ),
            "куплю бутылку у трактирщика": IntentProposal(
                "BUY", "bottle_1", "npc_oren", None, "visible offer and seller"
            ),
            "наберу воды в бутылку": IntentProposal(
                "USE", "bottle_1", "village_well", None, "owned bottle and local well"
            ),
            "уйду в тайный замок": IntentProposal(
                "MOVE", None, None, "secret_castle", "hallucinated destination"
            ),
        }

    def resolve(self, text, context):
        return self.proposals[text]


def main() -> None:
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="sam-sebe-natural-language-") as temp_dir:
        db = GameDatabase(Path(temp_dir) / "game.db")
        db.initialize()
        db.bootstrap_if_empty(now)
        app = DiscordGameApplication(
            GameService(db, FakeClock(now)),
            intent_resolver=DemoSemanticResolver(),
        )

        steps = [
            ("подберу плоский камень", "nl-demo-take"),
            ("пойду к таверне", "nl-demo-move"),
            ("швырну камень в вывеску", "nl-demo-throw"),
            ("куплю бутылку у трактирщика", "nl-demo-buy"),
            ("наберу воды в бутылку", "nl-demo-use"),
        ]
        for text, interaction_id in steps:
            response = app.handle_act("demo-semantic", "Ren", text, interaction_id)
            assert response.startswith("✅") or response.startswith("##")
            print(f"[natural] {text}")

        me = app.handle_me("demo-semantic", "Ren")
        assert "**Монеты:** 7" in me
        assert "внутри: water" in me
        look = app.handle_look("demo-semantic", "Ren")
        assert "состояние: 80%" in look
        print("[canonical] natural phrases produced the same BUY/USE/damage state as explicit commands")

        with db.connect() as conn:
            events_before = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
        rejected = app.handle_act(
            "demo-semantic",
            "Ren",
            "уйду в тайный замок",
            "nl-demo-hallucination",
        )
        assert "не понял" in rejected.casefold()
        with db.connect() as conn:
            events_after = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
            location = conn.execute(
                """
                SELECT a.location_id
                FROM actors a JOIN players p ON p.actor_id = a.id
                WHERE p.discord_user_id = 'demo-semantic'
                """
            ).fetchone()[0]
        assert events_after == events_before
        assert location == "village_square"
        print("[guardrail] hallucinated secret_castle was rejected before GameService/event creation")
        print("\nNatural-Language Intent contract demo: PASS")


if __name__ == "__main__":
    main()
