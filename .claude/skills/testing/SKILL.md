---
name: testing
description: Use when creating, refactoring, reviewing, or explaining tests in this Python FastAPI repository, including pytest unit tests, async tests, thin integration tests, FastAPI TestClient/httpx tests, svcs DI test wiring, reusable fakes under tests/fake_implementations, fixtures, conftest placement, and avoiding brittle mocks.
---

# Testing

Use this skill to keep Python tests behavior-focused, fake-first, and aligned
with this repository's `pytest`, FastAPI, async, and `svcs` composition patterns.

Pair with `fastapi-service` for API tests, `rest-api-design` for HTTP contract
coverage, and `clean-architecture` for boundary placement. Before changing DI
test wiring, read `docs/patterns/svcs_notes.md`.

## Core Testing Preference

- Prefer real domain objects and real application services.
- Prefer fakes over mocks when a dependency has meaningful behavior or state.
- Use mocks/spies only when a fake would be meaningless boilerplate, when the
  interaction itself is the behavior, or when a lightweight observer is clearer
  than a fully wired fake.
- Keep tests independent; each test gets fresh mutable state.
- Use explicit setup over hidden magic unless shared setup has proven reuse.
- Test observable behavior: returned values, persisted state, emitted events,
  queue messages, HTTP responses, and lifecycle effects.
- Avoid tests that only prove mocks were passed around.

## Test Double Guidance

Use a fake when:

- the dependency has state across calls
- the dependency represents persistence, queues, event logs, clocks, workers,
  external clients, auth providers, or service boundaries
- the fake helps test real application behavior
- the implementation can be reused across multiple tests

Use a stub when:

- the dependency only needs to return fixed data
- the behavior does not matter to the test
- a full fake would add noise without increasing confidence

Use `unittest.mock.Mock`, `AsyncMock`, or a small spy object when:

- verifying an outbound side effect such as event publishing, metrics, email,
  HTTP call, retry, or cancellation signal
- simulating an exceptional path that is hard to trigger with a fake
- collecting observed inputs into a list/container is simpler than building a
  fake implementation

Avoid asserting internal method calls unless the interaction is the actual
contract being tested.

## Reusable Test Support

Start local. Extract only after repetition appears.

Recommended growth path:

1. Inline setup inside one test.
2. Local helper or local fake inside one test file.
3. Folder-specific `conftest.py` when reused by nearby tests.
4. Shared fake, registrar, or factory under `llm_agent/tests/fake_implementations`
   when reused across test categories or feature folders.
5. Higher-level `conftest.py` only when reuse crosses multiple sibling folders.

Do not create a large root `conftest.py`. Keep fixtures close to the tests that
need them and move them upward only when reuse justifies it.

## Test Categories

- Unit tests: domain logic and services by direct construction; no FastAPI app,
  no database, no `svcs` container unless the unit under test is DI itself.
- Thin integration tests: integration between multiple in-process parts, such as
  service plus in-memory store, consumer plus queue/event log, or app DI
  composition with fake registrars.
- API tests: FastAPI `TestClient` or `httpx.AsyncClient` through ASGI; assert
  validation, status codes, DTOs, auth behavior, and error translation.
- Infrastructure integration tests: concrete adapters against real resources;
  isolate and mark them because they are slower and more environment-sensitive.
- Worker/async tests: assert event sequence, folded state, cancellation,
  idempotency, retry, and duplicate-processing behavior.

## DI And App Tests

- Use fake registrars and `ApplicationDIConfig` rather than monkey-patching
  production modules.
- Use `DependencyOverrideRegistrar` for small factory/value overrides.
- Use `ComposableRegistrarProvider` when a test needs to extend the development
  registrar provider.
- Put reusable fake registrars under `llm_agent/tests/fake_implementations`.
- Remember that later `svcs` registrations override earlier ones; if a container
  has already acquired a dependency, reset/close that container before expecting
  an override to take effect.

## Fixtures And conftest

- Prefer function-scoped fixtures for mutable state.
- Use `yield` fixtures for lifecycle resources that need cleanup.
- Avoid `autouse=True` unless the effect is truly cross-cutting and obvious.
- Avoid fixture chains that hide the scenario being tested.
- Name fixtures after the role they play in the test, not after the production
  implementation detail.

## Async Testing

- Use `pytest.mark.asyncio` for async tests.
- Use `asyncio.Event`, controlled fakes, and `asyncio.wait_for()` to make
  concurrent behavior deterministic.
- Avoid arbitrary sleeps. If a sleep is necessary, keep it short and explain the
  timing assumption.
- Always clean up background tasks in `finally`; cancel and await tasks so tests
  do not leak work into the next test.

## Implementation Workflow

When adding or refactoring tests:

1. Inspect the production boundary being tested.
2. Identify the observable behavior worth protecting.
3. Choose the smallest test category that gives confidence.
4. Construct the real subject under test.
5. Add fakes for dependency ports when behavior/state matters.
6. Use spies/mocks only for narrow observed interactions.
7. Keep setup local until reuse proves it should move.
8. Run the relevant `pytest` command when possible.

## Documentation Resources

Read `references/examples.md` when you need concrete Python examples for:

- fake implementations
- lightweight spies
- DI override registrars
- FastAPI `TestClient` fixtures
- folder-specific `conftest.py`
- async event-driven tests
