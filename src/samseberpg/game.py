from __future__ import annotations

from uuid import uuid4

from .clock import Clock
from .db import DEFAULT_WORLD_ID, GameDatabase
from .domain import VisibleActor, VisibleEntity, WorldView


class GameService:
    def __init__(self, db: GameDatabase, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def register_player(self, discord_user_id: str, name: str) -> str:
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT actor_id FROM players WHERE discord_user_id = ?",
                (discord_user_id,),
            ).fetchone()
            if row is not None:
                conn.execute("COMMIT")
                return str(row[0])

            player_id = f"player_{uuid4().hex}"
            created_at = _timestamp(self.clock)
            conn.execute(
                "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
                "VALUES (?, ?, 'player', ?, 'workshop_yard', ?)",
                (player_id, DEFAULT_WORLD_ID, name, created_at),
            )
            conn.execute(
                "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
                "VALUES (?, ?, ?, 10)",
                (player_id, discord_user_id, created_at),
            )
            conn.execute("COMMIT")
            return player_id
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def observe(self, player_id: str) -> WorldView:
        with self.db.connect() as conn:
            player = conn.execute(
                "SELECT actors.location_id, locations.name, locations.description "
                "FROM players "
                "JOIN actors ON actors.id = players.actor_id "
                "JOIN locations ON locations.id = actors.location_id "
                "WHERE players.actor_id = ?",
                (player_id,),
            ).fetchone()
            if player is None:
                raise LookupError(f"player not found: {player_id}")

            location_id = str(player[0])
            actor_rows = conn.execute(
                "SELECT id, name, actor_type FROM actors "
                "WHERE location_id = ? AND id <> ? ORDER BY actor_type, name, id",
                (location_id, player_id),
            ).fetchall()
            entity_rows = conn.execute(
                "SELECT id, name, entity_type, portable FROM entities "
                "WHERE location_id = ? AND owner_actor_id IS NULL ORDER BY name, id",
                (location_id,),
            ).fetchall()
            inventory_rows = conn.execute(
                "SELECT id, name, entity_type, portable FROM entities "
                "WHERE owner_actor_id = ? ORDER BY name, id",
                (player_id,),
            ).fetchall()

        return WorldView(
            player_id=player_id,
            location_id=location_id,
            location_name=str(player[1]),
            location_description=str(player[2]),
            visible_actors=tuple(_visible_actor(row) for row in actor_rows),
            visible_entities=tuple(_visible_entity(row) for row in entity_rows),
            inventory=tuple(_visible_entity(row) for row in inventory_rows),
        )


def _visible_actor(row) -> VisibleActor:
    return VisibleActor(actor_id=str(row[0]), name=str(row[1]), actor_type=str(row[2]))


def _visible_entity(row) -> VisibleEntity:
    return VisibleEntity(
        entity_id=str(row[0]),
        name=str(row[1]),
        entity_type=str(row[2]),
        portable=bool(row[3]),
    )


def _timestamp(clock: Clock) -> str:
    return clock.now().isoformat(timespec="milliseconds").replace("+00:00", "Z")
