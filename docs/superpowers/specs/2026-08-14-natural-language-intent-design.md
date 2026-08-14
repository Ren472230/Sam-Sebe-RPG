# Natural-Language Intent Provider — Design Specification

## Goal

Let a player write ordinary natural language such as “подберу плоский камень” or “швырну камень в вывеску таверны” while preserving the core invariant that an LLM may only propose intent. `GameService` remains the only authority that validates and mutates canonical state.

The slice succeeds when a semantic provider can map free-form text to a strictly bounded `CanonicalAction` using only canonical IDs visible/reachable to the player, invalid or hallucinated proposals cannot reach mutation, exact deterministic commands still work with zero AI cost, and provider failure leaves world state untouched.

## Resolution pipeline

```text
Discord /act text
      |
      v
exact deterministic parser --------------------------+
      | miss                                          |
      v                                               |
IntentContext from canonical WorldView                |
      |                                               |
      v                                               |
IntentResolver (optional Ollama)                      |
      |                                               |
      v                                               |
IntentProposal                                        |
      |                                               |
strict context validator / canonicalizer              |
      |                                               |
      +---------------- CanonicalAction <-------------+
                              |
                              v
                         GameService
                              |
                              v
                    deterministic rules + SQLite
```

The LLM never receives a DB connection, never emits SQL, never returns an `ActionResult`, and cannot write entity/relation/money state.

## Exact parser first

Existing explicit grammar remains the first path. This has three benefits:
- known commands stay deterministic and instant;
- no local model call is needed for repeated/test commands;
- LLM availability cannot break the existing playable surface.

The semantic provider is only consulted after `parse_action()` returns `None`.

## WorldView and IntentContext

`WorldView` gains `exits: tuple[str, ...]`, populated from canonical `location_edges`. `/look` renders these exits so the player can understand movement options.

`IntentContext` is a read-only projection containing:
- player ID and current location;
- adjacent exit IDs;
- visible actor IDs + names/types;
- visible entity IDs + names/types/state;
- inventory entity IDs + names/types/state;
- player coin balance.

It is built from `WorldView`; the provider never queries SQLite directly.

## IntentProposal

Internal proposal fields:
- `action_type`: `LOOK | MOVE | TAKE | DROP | THROW | GIVE | BUY | USE | UNSUPPORTED`;
- `item_id`: string or null;
- `target_id`: string or null;
- `destination_id`: string or null;
- `reason`: short string.

`UNSUPPORTED` is essential: the model must have a safe answer when the requested mechanic is outside the current whitelist instead of being forced to invent the nearest action.

## Strict canonicalization

A proposal is accepted only when its references are legal in the current `IntentContext`:

- LOOK: no IDs required;
- MOVE: destination must be one of `exits`;
- TAKE: target must be a visible entity;
- DROP: target/item must be owned inventory;
- THROW: item must be inventory and target must be a visible entity;
- GIVE: item must be inventory and target must be a visible actor;
- BUY: item must be visible and seller target must be a visible actor;
- USE: item must be inventory and target must be a visible entity;
- UNSUPPORTED: never becomes a `CanonicalAction`.

Unexpected IDs, action names, field types or impossible field combinations resolve to `None` and create no `action_events` row. `GameService` still performs its full deterministic gameplay validation afterward; context validation is only an extra guardrail.

## Resolver interface

```python
class IntentResolver(Protocol):
    def resolve(self, text: str, context: IntentContext) -> IntentProposal: ...
```

Provider failures raise `IntentResolutionError`. Discord catches only this expected provider error and returns a non-mutating fallback message. Programmer errors are not broadly swallowed.

## Ollama provider

`OllamaIntentResolver` uses Python stdlib HTTP; no Ollama Python dependency is required.

Runtime request:
- `POST {base_url}/api/chat`;
- non-streaming response;
- JSON Schema passed in `format`;
- `temperature: 0`;
- one system message defining the intent-only role;
- one user message containing player text plus compact canonical context;
- short configurable HTTP timeout.

Response `message.content` is parsed as JSON and validated again locally even though structured output was requested.

Default local base URL: `http://127.0.0.1:11434`.

No model name is guessed. Ollama semantic parsing is enabled only when `OLLAMA_MODEL` is explicitly configured. Otherwise the game keeps deterministic parser-only behavior.

Optional runtime configuration:
- `OLLAMA_MODEL` — enables semantic provider;
- `OLLAMA_URL` — default `http://127.0.0.1:11434`;
- `OLLAMA_TIMEOUT_SECONDS` — default 5, bounded to a reasonable positive value.

## Prompt/data safety

- Player text is data inside the user payload, not concatenated into the system policy.
- The system message explicitly says to ignore player attempts to alter parser rules.
- Only supported action names and current canonical IDs are permitted.
- Model-provided names/reasons are never canonical identifiers unless they match the allow-list exactly.
- No provider output is used as narrative truth or database state.

## Discord behavior

`DiscordGameApplication` accepts an optional `IntentResolver`.

On `/act`:
1. register/load player;
2. try exact parser;
3. on miss and resolver configured, observe canonical world and resolve semantically;
4. strict-canonicalize proposal;
5. if valid, call existing `GameService.execute(..., external_id=interaction_id)`;
6. otherwise return a compact “не понял/пока не поддерживается” response plus current help.

Existing callers that do not supply a resolver keep current behavior unchanged.

## Testing

No live model/network is required for automated tests.

Required tests:
- WorldView exposes only adjacent exits and `/look` renders them;
- canonicalizer accepts each valid action family;
- hallucinated/non-visible IDs are rejected with zero new events;
- `UNSUPPORTED` is rejected safely;
- exact parser wins and resolver is not called;
- fake resolver enables natural-language TAKE/MOVE/THROW/BUY/USE through Discord application;
- typed resolver failure produces no event/mutation;
- Ollama request includes model, `stream=false`, JSON Schema `format`, temperature 0 and canonical context;
- Ollama invalid JSON / invalid payload / HTTP failures become `IntentResolutionError`;
- runtime config enables Ollama only when `OLLAMA_MODEL` is present;
- no module except `ollama_intent.py` performs Ollama HTTP protocol work;
- all previous 55+ tests remain green.

## Environment limitation

This development environment has no local `ollama` binary/model, so this slice can verify the provider protocol, strict validation and end-to-end integration with fake/mocked provider responses, but cannot honestly claim a real model inference has been executed here.

## Definition of Done

Natural-language input can traverse a tested semantic-provider path into the same authoritative `GameService`; proposals are constrained to current canonical context; unsupported/hallucinated/provider-failure cases cannot mutate the world; deterministic commands still work without AI; Ollama runtime wiring is optional and dependency-free; full regressions and provider-contract demos pass.
