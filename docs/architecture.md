# Architecture – Сам-себе-RPG

## Principle

GitHub repository is the source of truth for development.

The game is split into systems, assets, tests and build output.

## Target structure

```
docs/
src/
assets/
standalone/
tests/
tools/
```

## Runtime layers

```
UI / adapters
      |
Game services
      |
World rules + simulation
      |
Persistence
```

## World model

The Living World layer owns:

- NPC state;
- schedules;
- consequences;
- events;
- persistent changes.

## Development rules

- Core state changes require tests.
- Architecture decisions are documented.
- Build artifacts are generated from source.
