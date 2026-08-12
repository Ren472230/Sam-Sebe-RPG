from __future__ import annotations

import argparse
import json
from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.reporting import build_playtest_report


def render_human(report: dict[str, object]) -> str:
    lines = [
        "=== Founder Playtest Report ===",
        f"Игрок: {report['player_id']}",
        f"Время мира: {report['world_time']}",
        f"Всего событий: {report['total_events']}",
        f"Неудачных событий: {report['failed_events']}",
        f"Типов действий: {report['unique_action_types']}",
        "Действия:",
    ]
    action_counts = report["action_counts"]
    assert isinstance(action_counts, dict)
    if action_counts:
        for action, count in action_counts.items():
            lines.append(f"  {action}: {count}")
    else:
        lines.append("  нет")

    throwing = report["throwing"]
    assert isinstance(throwing, dict)
    lines.extend(
        [
            "Броски:",
            f"  attempts: {throwing.get('attempts', 0)}",
            f"  hits: {throwing.get('hits', 0)}",
            f"  targets: {', '.join(throwing.get('targets', [])) or 'нет'}",
            f"  projectile_types: {', '.join(throwing.get('projectile_types', [])) or 'нет'}",
            f"  locations: {', '.join(throwing.get('locations', [])) or 'нет'}",
            "Achievements: " + (", ".join(report["achievements"]) or "нет"),
            "Abilities: " + (", ".join(report["abilities"]) or "нет"),
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline founder playtest report")
    parser.add_argument("db", type=Path, help="Путь к SQLite-файлу игровой сессии")
    parser.add_argument("--json", action="store_true", help="Вывести JSON")
    args = parser.parse_args(argv)

    if not args.db.exists():
        parser.error(f"database not found: {args.db}")

    db = GameDatabase(args.db)
    report = build_playtest_report(db)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
