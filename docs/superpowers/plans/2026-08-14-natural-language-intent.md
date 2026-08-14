# Natural-Language Intent Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a bounded semantic intent layer so free-form player text can propose existing canonical actions without giving an LLM authority over world state.

**Architecture:** Exact parser remains first. On a miss, a provider receives a canonical `IntentContext`, returns a strict `IntentProposal`, and a local validator converts only context-legal proposals to `CanonicalAction`. `GameService` is unchanged as final authority. Ollama is one optional HTTP provider behind the protocol.

**Tech Stack:** Python 3.12 stdlib (`dataclasses`, `json`, `urllib`), existing sqlite3/pytest project, optional external Ollama runtime with no Python SDK dependency.

## Constraints

- LLM/provider never writes SQLite.
- No new gameplay action types in this slice.
- Exact parser stays zero-AI and takes precedence.
- Semantic proposals may reference only canonical IDs in current player context.
- Provider errors/unsupported actions create no gameplay event.
- No live Ollama claim without a model runtime.

### Task 1: Canonical exits and intent context

**Files:** `domain.py`, `game.py`, `presentation.py`, new `intent.py`, tests.

- [ ] RED: WorldView exposes only current adjacent exit IDs and `/look` renders them.
- [ ] Add `exits` to WorldView and observation query.
- [ ] Add immutable `IntentContext`/context builder from WorldView.
- [ ] GREEN full suite.

### Task 2: IntentProposal and strict canonicalizer

**Files:** `intent.py`, new `tests/test_intent.py`.

- [ ] RED matrix for valid LOOK/MOVE/TAKE/DROP/THROW/GIVE/BUY/USE proposals.
- [ ] RED for unsupported action, unknown IDs, out-of-context inventory/targets/destinations and malformed fields.
- [ ] Implement `IntentProposal`, `IntentResolver` protocol, `IntentResolutionError`, and `canonicalize_proposal()`.
- [ ] Confirm rejected proposals produce no `CanonicalAction`.
- [ ] GREEN full suite.

### Task 3: Optional resolver path in Discord application

**Files:** `discord_app.py`, `tests/test_discord_app.py` or new intent integration tests.

- [ ] RED: exact parser does not call resolver.
- [ ] RED: fake resolver maps ordinary phrases into TAKE/MOVE/THROW/BUY/USE and reaches GameService.
- [ ] RED: hallucinated proposal/provider failure returns fallback with zero mutation/event.
- [ ] Add optional resolver constructor dependency and parser-miss flow.
- [ ] GREEN full suite.

### Task 4: Ollama structured-output HTTP provider

**Files:** new `ollama_intent.py`, `tests/test_ollama_intent.py`.

- [ ] RED with mocked `urlopen`: assert `/api/chat` payload has configured model, `stream=false`, JSON Schema `format`, `options.temperature=0`, system role and canonical context.
- [ ] Implement stdlib HTTP POST with short timeout.
- [ ] Parse top-level response then `message.content`; validate exact proposal payload locally.
- [ ] RED/GREEN invalid JSON, missing fields, invalid action/ID field types, HTTP/timeout errors -> `IntentResolutionError`.
- [ ] No network in unit tests.

### Task 5: Runtime selection and founder configuration

**Files:** `discord_bot.py`, runtime tests, README.

- [ ] RED: no `OLLAMA_MODEL` -> resolver disabled; model set -> `OllamaIntentResolver` configured with URL/timeout.
- [ ] Extend `RuntimeConfig` and `_build_application`.
- [ ] Document `OLLAMA_MODEL`, `OLLAMA_URL`, `OLLAMA_TIMEOUT_SECONDS` and the fact that exact grammar still works when Ollama is off.
- [ ] GREEN full suite.

### Task 6: End-to-end semantic contract demo and verification

**Files:** new `scripts/demo_natural_language.py`.

- [ ] Use a deterministic fake semantic resolver (not a fake LLM claim) to demonstrate ordinary-language phrases flowing through context validation into GameService.
- [ ] Include one hallucinated-ID proposal and prove no event/mutation.
- [ ] Run compileall, full pytest, all prior demos, new semantic demo and concurrency regression ×10.
- [ ] Sync exact verified blobs to feature branch.
