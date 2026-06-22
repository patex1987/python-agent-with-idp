# Dialogue Message Vertical Slice Review

Last reviewed: 2026-06-19

Scope: review of the no-LLM `Dialogue` / `Message` vertical slice on branch
`issue-1-dialogue-message-vertical-slice`.

This is a follow-up backlog document, not a release blocker list. Some findings
are intentionally future-facing because the current slice is in-memory and
demo-oriented.

## Review Inputs

- `agent-inspiration` local index:
  - `/home/patex1987/development/gh_agent_projects/_index/tag-map.md`
  - `/home/patex1987/development/gh_agent_projects/_index/patterns/runtime-state.md`
  - `/home/patex1987/development/gh_agent_projects/_index/patterns/orchestration-evaluation-ops.md`
  - `/home/patex1987/development/gh_agent_projects/_index/patterns/context-knowledge-steering.md`
  - `/home/patex1987/development/gh_agent_projects/_index/patterns/tools-policy-security.md`
- Project policy: `docs/knowledge/agent-inspiration-sources.md`
- Clean architecture skill: `.codex/skills/clean-architecture/SKILL.md`
- Review subagents:
  - system design / scalability
  - security practices
  - performance / scalability
  - readability / maintainability

No internet research was used.

## Overall Verdict

The slice is directionally right:

- Public API is now `Dialogue` / `Message` based.
- `AgentExecution` is internal and no longer exposed as a frontend resource.
- The implementation uses directional CP -> DP and DP -> CP style ports.
- Internal events are versioned dataclasses instead of unstructured strings.
- Tooling, shell execution, filesystem edits, approvals, MCP, and real LLM calls
  remain deferred, which matches the local inspiration index separation between
  runtime state and tool/security policy.

The main weaknesses are not naming or route shape. They are runtime correctness
and operability concerns:

- dispatch/link atomicity is now guarded in-memory; durable persistence still
  needs a transaction/outbox boundary
- cancellation/success races are now guarded in-memory; durable persistence
  still needs conditional terminal updates/fence tokens
- message projection is now event-based by `agent_execution_id`; durable
  projection retry/outbox and repair scans are still missing
- security/auth and event redaction need hardening before richer agent behavior

## Agent Inspiration Fit

Local index says runtime/state patterns should separate:

- session/thread -> `Dialogue`
- message/input/output -> `Message`
- run/task/job/execution -> `AgentExecution`

The implementation follows that vocabulary well.

Local index says event logs, checkpointing, cancellation, idempotency, and
resumability are runtime-state concerns. The slice has the beginnings of this:
typed event envelope, worker claim/lease, cooperative cancellation, and message
projection. It does not yet have expected-version writes, idempotency, durable
projection checkpoints, or durable recovery.

Local index says tools, approvals, permission policy, sandboxing, secrets, and
filesystem edits are a separate safety cluster. Deferring tools is the right
choice. Before adding tools, the project needs idempotency, redaction, audit
events, and a permission policy boundary.

Local index says context management, prompt assembly, retrieval, and skill
loading should be loaded deliberately. The slice creates typed history snapshots,
but there is no context assembly service yet. That is fine for no-LLM execution,
but it should be designed before model calls.

## Clean Architecture Check

What looks good:

- Domain objects and shared contracts do not import FastAPI, Pydantic, Piccolo,
  `svcs`, or concrete adapters.
- API routes own HTTP translation and map domain/service errors into API errors.
- `DialogueService` depends on service/store ports and internal execution
  control service rather than FastAPI.
- In-memory runtime lives outside the domain layer.

Boundary findings and status:

- Default composition now registers the in-memory `DialogueService` and worker
  graph through real registrars. Follow-up: replace the in-memory default with
  durable production adapters when persistence is introduced.
- The local development provider still lives under `tests.fake_implementations`,
  but its agent-execution registrars are now compatibility wrappers over the
  real in-memory registrars. This remains an accepted temporary guardrail so
  fake local-development deps are not accidentally loaded by production images;
  revisit with an explicit demo/development provider.
- Worker runtime still invokes control-plane projection inline as a wakeup, but
  projection now reads terminal execution events from the event log and can be
  replayed by `agent_execution_id`. Follow-up: move projection wakeups to a
  durable outbox/projector worker before persistence.
- `AgentExecutionIntakeStore.mark_cancelled()` was removed after review.
  Control-plane cancellation now records intent only; terminal cancellation
  remains on the worker/processing side.

## Prioritized Findings

### P0: Default App Composition Is Broken

Status: partially addressed in this branch. The default registrar graph now
registers the in-memory dialogue/execution service graph and an in-memory worker
consumer outside `tests.fake_implementations`. A durable production adapter is
still a follow-up.

Evidence:

- At review time, `llm_agent/llm_agent/di/fastapi_composition.py` defaulted to production
  registrars.
- `llm_agent/llm_agent/di/fastapi_composition.py` always builds infrastructure
  by resolving `Consumer`.
- At review time, `llm_agent/llm_agent/di/app_registrar_providers.py` registered no
  infrastructure registrars.
- At review time, `llm_agent/llm_agent/di/registrars/agent_execution.py` was a no-op.
- `llm_agent/llm_agent/app.py` registers dialogue routes that require
  `DialogueService`.

Impact:

At review time, the default app profile could fail at startup or request time.
The default app graph now starts with in-memory agent execution wiring. The
remaining concern is making the eventual durable production graph explicit.

Remaining recommendation:

- Keep the real in-memory registrar implementation outside `tests/`.
- Add a no-op infrastructure setup when a provider intentionally has no
  consumer, or make that unsupported profile fail fast with a clear startup
  error.
- Add a separate local/demo composition smoke test if the provider remains
  under `tests.fake_implementations`.

### P0: Execution Can Be Dispatched Before Assistant Message Linking

Status: addressed for the in-memory vertical slice. `DialogueService` now uses
an `AssistantResponseSubmissionStore` preparation boundary, and dispatch happens
only after the assistant message is linked and the execution has been marked
ENQUEUED. A regression test simulates immediate completion during dispatch.

Evidence:

- At review time, `DialogueService.create_user_message()` created user and
  assistant messages.
- At review time, it called `AgentExecutionControlService.create_agent_execution()`.
- At review time, `AgentExecutionControlService.create_agent_execution()` created,
  enqueued, and dispatched the execution before returning.
- At review time, `DialogueService` linked `assistant_message_id -> agent_execution_id` only
  after dispatch returns.

Impact:

A fast worker can complete before the reverse mapping exists. Projection then
cannot find the assistant message, leaving a pending assistant response that can
block the dialogue.

Implemented recommendation:

- Split execution creation from dispatch.
- Create assistant placeholder and internal execution record first.
- Link assistant message to execution before making execution visible to the
  worker.
- Dispatch after the link is durable.
- Add a test with an immediate worker proving completion cannot outrun linking.

### P0: Message Creation, Execution Creation, Event Append, And Dispatch Are Not Atomic

Status: partially addressed for the in-memory vertical slice. The code now has a
compound `AssistantResponseSubmissionStore` boundary that mirrors the future DB
transaction/outbox boundary. The in-memory implementation compensates
preparation failures by marking the assistant placeholder failed so the dialogue
does not remain blocked. True process-crash atomicity still requires durable
persistence and an outbox.

Evidence:

- At review time, `DialogueService.create_user_message()` appended messages first.
- At review time, it created/enqueued/dispatched execution before linking the
  assistant message.

Impact:

Any failure in execution creation, enqueue, dispatch, or linking can leave a
stuck pending assistant message. That message can block future messages through
the active-response rule.

Implemented recommendation:

- For in-memory: add compensation that marks assistant message failed if
  preparation fails before the execution is ready for dispatch.
- For persistence: implement one transaction/outbox boundary for message pair,
  execution record, initial execution events, and dispatch intent.

### P0: Cancellation And Success Can Race

Status: addressed for the in-memory vertical slice. Intake and processing
adapters now delegate to one shared `InMemoryAgentExecutionState` coordinator
with one transition lock. `set_succeeded()` atomically re-checks
`cancel_requested` before emitting success, and a regression test covers a
stale worker success attempt after cancellation intent is recorded.

Evidence:

- At review time, intake cancellation and worker processing used different store instances and
  different locks over shared execution storage.
- At review time, worker success transition did not atomically re-check `cancel_requested`
  inside the transition path.

Impact:

A late cancellation can be lost and an execution can complete as succeeded after
the user has requested cancellation.

Implemented recommendation:

- In-memory: use one shared atomic local store/lock for CP and DP execution
  state mutations.
- Add a race test that requests cancellation while the worker is about to
  complete.

Remaining recommendation:

- DB later: use conditional terminal updates/fence tokens. Worker succeeds only
  if status is `RUNNING`, worker owns the lease, and `cancel_requested=false`.

### P0: JWT Audience Is Not Enforced

Evidence:

- JWT manager uses placeholder audience configuration.
- JWT validator has audience validation commented out.

Impact:

Any valid token from the configured issuer/realm may authenticate even if it was
minted for another client/application.

Recommendation:

- Configure expected audience/client ID from environment/config.
- Enforce `aud` and/or `azp`.
- Add wrong-audience rejection tests.

Status:

- Deferred for now by product/iteration decision.
- Code TODOs added near the placeholder audience and disabled validator claim.
- Follow-up tracked in `docs/plans/TODO.md`.

### P1: Message Projection Was Inline And Not Replayable

Evidence:

- Worker writes terminal execution state and immediately calls the completion
  sink.
- Completion handler directly mutates assistant messages.
- If projection fails after terminal state is written, the worker catch path may
  attempt an invalid terminal-to-failed transition.

Impact:

Internal execution state can be terminal while public assistant message remains
pending.

Recommendation:

- Make projection idempotent and retryable.
- Add a repair/replay path from terminal `AgentExecutionEvent`s to assistant
  message state.
- Later, move this toward an outbox/projector style worker instead of only an
  inline callback.

Status:

- Addressed for the in-memory slice with an event-based
  `DialogueAgentExecutionMessageProjector`.
- Worker projection failures are isolated from execution failures, so a failed
  projection cannot turn a terminal successful execution into failed.
- Projection can be replayed by `agent_execution_id` from terminal
  `AgentExecutionEvent`s and is duplicate-safe for the same terminal message
  projection.

Remaining follow-ups:

- Add a durable projection outbox/projector worker with retry policy and
  processed-event checkpoints.
- Add repair tooling that finds terminal executions whose assistant message is
  not terminal, not only repair by known `agent_execution_id`.
- Consider a separate full event-sourcing learning spike for
  `AgentExecution`/`Message` projection, but do not productize it until event
  schema migration, privacy, replay safety, and projection operations are
  designed.

### P1: Backlog Can Drain At One Item Per Wake/Timeout

Status: addressed for the in-memory consumer. After one wake, the worker now
claims and executes available work until `claim_agent_execution()` returns
`None`.

Evidence:

- Worker waits for a wake signal before every claim.
- It claims only one execution per wake.
- The in-memory signal is an `asyncio.Event` that coalesces notifications and is
  cleared after wait.

Impact:

Under burst load, the worker can process one item and then sleep until timeout
even though more work is already enqueued.

Recommendation:

- After a wake, loop `claim_agent_execution()` until it returns `None`.
- For future broker adapters, use queue depth/visibility semantics rather than
  treating the signal as a durable queue.

Remaining follow-up:

- When adding DB+Rabbit, DB+SQS, or Temporal adapters, define adapter-specific
  queue-depth, visibility, lease, and retry semantics. The in-memory signal must
  remain only a wake hint, not a durable queue contract.

### P1: Raw Worker Exception Text Is Persisted Into Events

Status: deferred. Do not fix inside the dialogue/message vertical-slice PR; keep
this as a dedicated security/ops hardening task before real model/tool
execution is added.

Evidence:

- Worker logs `str(exc)` and passes it to `set_failed()`.
- Processing store writes it into `AgentExecutionFailedPayload(error=str)`.

Impact:

Future model/tool exceptions can include prompts, file paths, credentials, env
values, or provider payloads. The event log can become a leakage surface.

Recommendation:

- Split safe error `{code, message, retryable}` from restricted diagnostics.
- Redact before event/log emission.
- Store raw diagnostic detail only in a controlled debug sink if needed.

Follow-up task:

- Design and implement a safe worker error contract for `AgentExecution` terminal
  failure events. The public/event-log payload should contain stable safe fields
  such as `code`, `message`, and `retryable`; restricted diagnostics should be
  redacted, access-controlled, and correlated by execution/message IDs rather
  than copied into normal events or logs.

### P1: Internal Cancellation Boundary Trusts AgentExecution ID Alone

Status: deferred. Do not expand the cancellation command contract inside the
dialogue/message vertical-slice PR; keep this as a focused authorization and
stale-ID hardening follow-up.

Evidence:

- Public route checks ownership through `DialogueService`.
- Internal `AgentExecutionControlService.request_cancellation()` accepts only
  `agent_execution_id`.
- Intake store mutates cancellation state by ID without expected
  `user_id/dialogue_id/message_id` validation.

Impact:

Today the public route is safe, but future admin/internal/debug paths could
cancel another user's execution if they pass a wrong or stale ID.

Recommendation:

- Make cancellation pass expected `user_id`, `dialogue_id`, and
  `assistant_message_id`.
- Validate those against `AgentExecutionStatus.request` before mutation.

Follow-up task:

- Harden the internal cancellation boundary so cancellation intent includes the
  expected `user_id`, `dialogue_id`, and `assistant_message_id`. The control
  service/store must validate those values against the original
  `AgentExecutionRequest` before mutating cancellation state, preventing stale
  or cross-dialogue execution IDs from cancelling the wrong work.

### P1: Stale Deprecated Cancellation Path Emits Wrong Payload

Status: addressed in this branch. The control-plane intake protocol and
in-memory intake store no longer expose `mark_cancelled()`.

Evidence:

- At review time, `AgentExecutionIntakeStore.mark_cancelled()` remained on the control-plane
  protocol.
- At review time, the in-memory intake implementation marked it deprecated.
- At review time, it emitted `agent_execution.cancelled` with
  `AgentExecutionCancelRequestedPayload`.

Impact:

Future contributors see two cancellation models and one can produce a
schema-inconsistent event.

Remaining recommendation:

- Keep terminal cancellation only on the worker/processing side.
- If a direct terminal cancel remains, emit `AgentExecutionCancelledPayload`.

### P1: Request And Worker Correlation Are Incomplete

Status: deferred. Keep this PR focused on the dialogue/message slice; revisit
correlation when onboarding OpenTelemetry, custom traces, and custom metrics.

Evidence:

- Event schema supports `request_id`, `user_id`, message IDs, and worker ID.
- `AgentExecutionRequest` does not carry `request_id`.
- Execution creation and executor-emitted progress events do not consistently
  fill correlation fields.

Impact:

On-call cannot reliably join HTTP request, dialogue, message, execution, worker,
and event records.

Recommendation:

- Carry request ID from request context into `AgentExecutionRequest`.
- Construct `AgentExecutionContext` with request snapshot and worker ID.
- Use a typed event emitter that always fills correlation fields.
- Add structured log fields for `dialogue_id`, `message_id`,
  `agent_execution_id`, `worker_id`, and `event_id`.

Follow-up task:

- Design end-to-end observability correlation across HTTP requests, dialogues,
  messages, agent executions, worker processing, events, logs, traces, and
  metrics. When OpenTelemetry is onboarded, make logs and traces auditable,
  researchable, and easy for on-call engineers to join by stable correlation
  fields such as `request_id`, `trace_id`, `user_id`, `dialogue_id`,
  `message_id`, `agent_execution_id`, `worker_id`, and `event_id`.

### P1: Unauthenticated Requests Can Become 500s

Status: addressed in this branch. Missing JWT tokens now raise
`AuthenticationError`, and middleware returns `401` instead of treating the
failure as an unexpected server error.

Evidence:

- JWT manager raises `PermissionError("Missing token")`.
- Authentication middleware maps only `AuthenticationError` to 401 and other
  exceptions to 500.

Impact:

Missing or malformed auth can look like server failure and hide auth regressions.

Recommendation:

- Raise `AuthenticationError` for missing tokens or catch `PermissionError` as
  authentication failure.
- Add no-token route tests.

### P2: Event Log Is Unbounded And Unpaginated

Status: deferred. Do not implement event-log pagination or retention in this
vertical-slice PR; design it before exposing public/realtime events or
progress-heavy workers.

Evidence:

- In-memory event log retains all event streams indefinitely.
- `list()` returns all events after an optional sequence without a limit.

Impact:

Long local sessions or progress-heavy executions can grow memory and slow event
reads.

Recommendation:

- Add limit/cursor to the event-log protocol before exposing public events.
- Define local retention expectations.

Follow-up task:

- Design event-log pagination and retention. Add `limit` plus cursor/sequence
  semantics to the event-log protocol, define local in-memory retention
  expectations, and decide durable retention/archival behavior before public
  event streams, SSE/websocket updates, or progress-heavy execution events are
  exposed.

### P2: In-Memory Stores Use Global Locks And Linear Scans

Status: accepted for the local in-memory runtime. The in-memory implementation
is intentionally simple and demo-focused; do not add indexing or per-dialogue
lock complexity in this PR. Production/dockerized persistence adapters should
own the scalable query/index design.

Evidence:

- Dialogue store has one global lock.
- Dialogue list sorts all matching dialogues.
- Message lookup scans message lists.
- Message replacement scans message lists.

Impact:

Heavy polling or large dialogues can delay unrelated users in local runtime.

Recommendation:

- For in-memory: maintain per-user dialogue indexes, per-dialogue message
  indexes, or at least per-dialogue locks.
- For Postgres: plan indexes on `(user_id, created_at DESC, id)`,
  `(dialogue_id, sequence_nr)`, `message_id`, and `agent_execution_id`.

Follow-up task:

- During the persistent-store slice, design the Piccolo/Postgres schema and
  indexes for dialogue/message/execution lookup patterns. Keep the local
  in-memory store simple unless it starts blocking development feedback loops.

### P2: Store Methods Await Event Log Operations While Holding Locks

Status: accepted for the local in-memory runtime. Do not split or optimize this
inside the fake/demo implementation in this PR. The production persistence
adapter must treat state mutation plus event append as one explicit
transactional boundary instead of awaiting remote work while holding a local
runtime lock.

Evidence:

- Intake and processing stores hold their locks while awaiting event log
  append/init operations.

Impact:

Safe enough with current in-memory append, but dangerous when event log becomes
database-backed or remote.

Recommendation:

- Keep in-memory critical sections short.
- For durable storage, make state mutation and event append one explicit
  transactional adapter.

Follow-up task:

- During the durable persistence slice, design the state-mutation plus
  event-append boundary as a single transactional adapter. For DB-backed
  implementations, persist the execution/message state changes and event rows in
  the same transaction or use an explicit outbox pattern; do not translate the
  in-memory lock shape into remote event-log calls under application locks.

### P2: Cancellation Latency Is Not Observable

Status: deferred into the observability/OpenTelemetry work. Do not implement
metrics or cancellation notification changes in this PR, but cancellation
latency must become first-class telemetry before production-style workers.

Evidence:

- Cancellation wakes the work signal, but running execution observes
  cancellation via heartbeat/checkpoint polling.
- Default heartbeat is several seconds.

Impact:

Cancellation can visibly lag, and there are no metrics to explain whether delay
comes from heartbeat, checkpoint duration, or backlog.

Recommendation:

- Track `cancel_requested_at` to terminal latency.
- Later, add targeted cancellation notification to active worker or make the
  lease loop wait on either heartbeat interval or cancellation wake.

Follow-up task:

- Add cancellation-latency telemetry as part of the observability slice. Emit or
  derive `cancel_requested_at`, cancellation observed time, checkpoint stop
  time, and terminal cancellation time so on-call can tell whether delay comes
  from heartbeat polling, long checkpoints, backlog, or projection/finalization.
  Revisit targeted active-worker cancellation notification after those metrics
  show whether it is needed.

### P2: DTOs Lose Enum Contract Information

Status: addressed in this branch. `MessageDto.role` and `MessageDto.status`
now use DTO-level `StrEnum`s so OpenAPI documents the allowed public values
without coupling the response schema directly to domain enum classes.

Evidence:

- Domain has `MessageRole` and `MessageStatus`.
- `MessageDto.role` and `MessageDto.status` are plain strings.

Impact:

OpenAPI does not communicate allowed values clearly.

Recommendation:

- Use DTO-level `StrEnum`s or deliberately reuse domain enums in response DTOs.

### P2: Unit Coverage Is Thin

Status: partially addressed in this branch. Added a minimum unit-test floor for
`DialogueService` and history snapshot behavior. Broader test-suite strategy is
deferred to a dedicated follow-up.

Evidence:

- Main coverage is thin integration.
- There are no isolated unit tests for `DialogueService`,
  `InMemoryDialogueStore`, event contracts, DTO mapping, or history snapshot
  construction.

Impact:

Future failures will be harder to localize as the slice grows.

Recommendation:

- Add unit tests for service/store/event-contract behavior.
- Keep integration tests for route + worker flow.
- Avoid relying on private test executor fields where small public test helper
  methods would be clearer.

Follow-up task:

- Revamp the project testing strategy and suite structure across unit tests,
  thin integration tests, Testcontainers-backed infrastructure/e2e tests, and
  system tests such as synthetic load and in-cluster checks. Define what each
  layer is responsible for, what must not be tested there, naming/location
  conventions, fixtures/fakes, required CI stages, and local developer commands.

### P2: Generated AI Guidance Still Has Stale Vocabulary

Status: addressed. Canonical `.ai/` guidance now uses dialogue/message/
agent-execution vocabulary for project layout, REST examples, testing examples,
security review focus, and worker/event guidance. Generated tool guidance was
refreshed with `.ai/sync.sh`.

Original evidence:

- Generated guidance referenced old worker paths in places.
- Skill examples included old `Run`/`Conversation` examples.

Impact:

Humans and future AI agents can reintroduce old terminology.

Recommendation:

- Update canonical `.ai/` guidance and skill examples.
- Run `.ai/sync.sh`.

### P2: Local Env Files May Contain Real API Keys

Status: deferred for an explicit env-template cleanup in this PR. Do not copy
or quote any existing values into docs, logs, issue comments, or review notes.

Evidence:

- A reviewer reported non-empty API-key-looking values in local env files under
  `configuration/env_files/`.

Impact:

If real, these values are secret material and should not live in repo state.

Recommendation:

- Inspect without copying values into docs or logs.
- Rotate/remove if real.
- Keep sample env files placeholder-only.
- Split committed env configuration into placeholder-only templates.
- Add generated/rendered local env files to `.gitignore`.
- Add a short guide explaining how developers render/fill templates for their
  chosen local or Docker usage.

## Suggested Follow-Up Order

Detailed follow-up work moved to
[`docs/plans/follow-ups/`](../plans/follow-ups/README.md). Use this priority
order:

1. [P0 current PR hygiene](../plans/follow-ups/p0-current-pr-hygiene.md)
2. [P1 safety and control-plane hardening](../plans/follow-ups/p1-safety-control-plane-hardening.md)
3. [P1 observability and operations](../plans/follow-ups/p1-observability-operations.md)
4. [P1 persistence and runtime reliability](../plans/follow-ups/p1-persistence-runtime-reliability.md)
5. [P2 testing strategy](../plans/follow-ups/p2-testing-strategy.md)
6. [P2 agent product capabilities](../plans/follow-ups/p2-agent-product-capabilities.md)
7. [P3 learning spikes](../plans/follow-ups/p3-learning-spikes.md)

## Non-Goals For The Next Patch

- Do not add real LLM/model calls before atomicity and projection are safer.
- Do not add shell/filesystem/tool execution before idempotency, safe errors,
  approvals, permission policy, and audit vocabulary exist.
- Do not expose raw internal execution events publicly. Design a transformed
  client-safe message event stream later.
