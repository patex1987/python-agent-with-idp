# Implementation Plan: Demo Multi-Service Observability Agent Worker

## 1. Summary

Build a demo-focused FastAPI agent worker in this repository for the multi-service observability flow:

```text
client -> movie-agent-worker -> MCP tools -> service APIs -> traces/logs/metrics
```

The recommended approach is an additive demo slice under the existing FastAPI + `svcs` composition model. The service will expose `POST /api/v1/demo/reserve-recommended-seat` and `GET /api/v1/demo/health`, load static skill markdown into the agent context, discover/call MCP tools through FastMCP clients, run a small LangGraph ReAct-style workflow with a deterministic fallback planner, and emit OpenTelemetry traces/metrics plus structured JSON logs.

This is a design-review-level plan because the work is cross-cutting: API, DI, dependencies, external MCP clients, LLM orchestration, observability, Docker runtime config, and tests.

## 2. Goals

- Expose demo HTTP endpoints:
  - `POST /api/v1/demo/reserve-recommended-seat`
  - `GET /api/v1/demo/health`
- Accept demo reservation input with `movie_preference`, `seat_preference`, and `fault`.
- Accept and propagate `traceparent`, `tracestate`, `X-Correlation-Id`, and `X-Request-Id` to MCP tool calls.
- Load static skills from markdown files into the agent system/context prompt.
- Connect to these MCP servers:
  - `MOVIE_RESERVATION_MCP_URL`, defaulting to `http://movie-reservation-mcp:8091/mcp` in compose.
  - `AXUM_TOOLS_MCP_URL`, defaulting to `http://axum-tools-mcp:8092/mcp` in compose.
- Discover MCP tools and expose reliable wrappers for:
  - `recommendation_get_movies`
  - `movie_list_screenings`
  - `movie_request_reservation`
  - `movie_get_reservation_status`
  - `movie_get_reservation_result`
- Run the reservation workflow through a LangGraph graph with nodes:
  - `load_context`
  - `agent_reason`
  - `tool_call`
  - `observe`
  - `finalize`
- Work without a real LLM API key by using a deterministic planner.
- Use a real chat model when a supported model provider key/config is present.
- Emit structured ReAct logs for each workflow step.
- Instrument FastAPI inbound requests, FastMCP/httpx outbound calls, graph nodes, and MCP tool calls with OpenTelemetry.
- Dockerize the service as `movie-agent-worker` on port `8081` with the required OTel and MCP environment.

## 3. Non-goals

- Do not finish or redesign the existing throttle/game/navigation examples.
- Do not turn this into a production agent platform with persistent memory, vector search, tenant management, or user-driven skill installation.
- Do not introduce a database schema for demo runs unless a later requirement explicitly needs durable run history.
- Do not require a real LLM key for the demo path.
- Do not dynamically trust arbitrary MCP tools. The demo should discover tools but execute only the allowlisted workflow tools.
- Do not log raw tokens, secrets, full request bodies, or full provider payloads.
- Do not replace the existing `/api/v1/agent` run orchestration. Keep the demo route isolated.

## 4. Current State

Repository and branch:

- Current branch is `demo-multi-service-observability`, matching the mission document.
- The working tree was clean before writing this plan.

FastAPI and DI:

- `llm_agent/llm_agent/app.py` constructs the FastAPI app, configures logging, wraps lifespan with `svcs.fastapi.lifespan(...)`, includes routers, calls `instrument_for_telemetry(app)`, and runs migrations.
- Existing routers:
  - `llm_agent/llm_agent/api/http/v1/routes/health.py` mounted at `/api/v1/health`.
  - `llm_agent/llm_agent/api/http/v1/routes/agent.py` mounted at `/api/v1/agent`.
  - `llm_agent/llm_agent/api/http/v1/routes/throttle_steps_calculator.py` mounted at `/api/v1/throttle`.
- `llm_agent/llm_agent/di/fastapi_composition.py` is the composition root. It selects `DI_REGISTRAR_PROVIDER`, applies app-lifetime registrars, stores FastAPI lifespan registrars, builds infrastructure setup, and registers middleware.
- `docs/patterns/svcs_notes.md` confirms the intended pattern: registrars wire dependencies, routes stay thin, services do not call the container, tests override dependencies through registrars.

Auth and request context:

- `AuthenticationMiddleware` currently skips only paths starting with `"/health"`. The requested `/api/v1/demo/health` path will not be skipped unless this is changed.
- Production request context currently generates a short request ID in `ProductionContextEnricher.enrich_from_scope(...)`; it does not preserve inbound `X-Request-Id`, `X-Correlation-Id`, `traceparent`, or `tracestate`.
- `RequestContextVars` currently stores only `JWT_TOKEN`.

Telemetry and logs:

- `llm_agent/llm_agent/core/telemetry.py` is a stub:

```python
def instrument_for_telemetry(app):
    pass
```

- `llm_agent/llm_agent/core/log_config.py` configures structlog JSON logs and currently defaults `service_name` to `llm_agent_fastapi`.
- The mission requires `service_name=movie-agent-worker` in ReAct logs.

Dependencies:

- `llm_agent/pyproject.toml` already includes:
  - `fastapi`
  - `httpx`
  - `opentelemetry-api`
  - `opentelemetry-sdk`
  - `pydantic-settings`
  - `structlog`
  - `svcs`
  - `uvicorn`
- Missing for the demo:
  - `langgraph`
  - `langchain-core`
  - OpenRouter-compatible model access through `httpx`; no provider-specific SDK is required
  - `fastmcp`
  - `opentelemetry-exporter-otlp-proto-http`
  - `opentelemetry-instrumentation-fastapi`
  - `opentelemetry-instrumentation-httpx`

Docker and runtime config:

- `llm_agent/Dockerfile` has `dev` and `prod` targets, exposes `8080`, and healthchecks `/api/v1/health/dummy-health`.
- `docker-compose.yml` has one `llm-agent` service on port `8080`.
- Runtime env files are rendered from committed templates under `configuration/env_files/templates`; rendered env files are ignored by git and should not be committed.

Tests:

- Current tests are under `llm_agent/tests/thin_integration`.
- Test wiring uses fake registrars and `create_app_with_selected_di(...)`, which is the right extension point for demo service tests.
- There are no current tests for telemetry, MCP clients, demo routes, or agent workflow.

Useful external references checked:

- LangGraph official docs show `StateGraph`, nodes, edges, `compile()`, and invocation as the core graph API:
  - https://docs.langchain.com/oss/python/langgraph/overview
- FastMCP official docs show `Client("https://.../mcp")`, `async with client`, `list_tools()`, and `call_tool(...)`; they also document multi-server config with prefixed tools:
  - https://gofastmcp.com/clients/client
- OpenTelemetry Python contrib docs show `FastAPIInstrumentor.instrument_app(app)` and HTTP header capture/sanitization:
  - https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
- OpenTelemetry Python contrib docs show HTTPX instrumentation for outbound HTTP calls:
  - https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/httpx/httpx.html
- OpenTelemetry exporter docs confirm the OTLP exporter path for Python SDK setup:
  - https://opentelemetry.io/docs/languages/python/exporters/
- Local Programming KB notes used:
  - `/home/patex1987/Documents/programming_kb/concepts/Context Interfaces.md`
  - `/home/patex1987/Documents/programming_kb/patterns/Dockerized Local Dependency Stack.md`
  - `/home/patex1987/Documents/programming_kb/patterns/NestJS Request Context Middleware.md`

## 5. Requirements and Assumptions

### Confirmed Requirements

- This repo is the visible agent worker for the demo, not a production agent platform.
- Use FastAPI for HTTP.
- Use LangGraph for a simple ReAct loop.
- Use FastMCP client connections for tool discovery and invocation.
- Use hardcoded demo skills.
- Use OpenTelemetry for traces and metrics.
- Preserve and propagate `traceparent`, `tracestate`, `X-Correlation-Id`, and `X-Request-Id`.
- Support `fault` values:
  - `none`
  - `slow-recommendation`
  - `recommendation-error`
- If FastMCP multi-server prefixing complicates implementation, explicit clients and hardcoded wrappers are acceptable.
- The deterministic fallback planner must execute this sequence:

```text
recommendation_get_movies -> movie_list_screenings -> movie_request_reservation -> movie_get_reservation_status -> movie_get_reservation_result
```

### Assumptions

- The demo endpoints should be callable without JWT auth so the observability demo can be driven by curl and other services. Existing non-demo endpoints should keep their current auth behavior.
- `/api/v1/demo/health` should be unauthenticated.
- The `fault` value should be forwarded to the recommendation-related MCP tool payload or metadata so downstream services can trigger slow/error behavior.
- MCP servers accept trace/correlation/request context either as transport headers or as tool input metadata. The implementation should support HTTP headers first and include a fallback `metadata` argument only if server contracts require it.
- The response should be synchronous for demo simplicity: the POST endpoint should run the workflow and return the final result or a controlled error response.
- Static skills should live as markdown files in the package so they are included in the built wheel/container.
- The demo can keep run state in memory for the life of one request.
- Metrics can be minimal but real: workflow counter, tool-call counter, failure counter, and duration histogram.

### Open Questions

1. Which real LLM provider should be supported first if a key is present?
   - Plan default: OpenRouter behind `OPENROUTER_API_KEY`.
2. What exact MCP argument schema do the movie tools expect?
   - Plan default: inspect tool schemas from `list_tools()` and map with small per-tool adapters during implementation.
3. Should `recommendation-error` return HTTP `502` or a successful demo response with `outcome="dependency_failed"`?
   - Plan default: return `502` for dependency failure, with a structured response body and logs/spans carrying `outcome="dependency_failed"`.
4. Should `/api/v1/demo/reserve-recommended-seat` require JWT in non-demo environments?
   - Plan default: unauthenticated in this demo branch only; do not introduce environment-dependent auth unless requested.
5. Are the MCP services reachable by Docker DNS names or host gateway in the final compose topology?
   - Plan default: compose service uses container DNS names; host/IDE env uses `host.docker.internal` or `127.0.0.1`.

## 6. Proposed Design

### Component Overview

Add a new demo slice with these responsibilities:

```text
api/http/v1/routes/demo.py
  -> validates HTTP request, extracts propagation headers
  -> calls DemoReservationService
  -> maps service result/failures to response DTOs

services/demo/reservation_service.py
  -> owns use-case orchestration boundary
  -> calls AgentWorker

demo/skills.py + demo/skills/*.md
  -> loads static markdown skills by name

demo/mcp_client.py
  -> creates per-request FastMCP clients
  -> lists tools
  -> exposes allowlisted typed wrappers
  -> propagates trace/correlation/request context

demo/agent_worker.py
  -> defines state type
  -> builds LangGraph graph
  -> deterministic fallback planner
  -> optional model-backed reasoner
  -> manual spans/log events per node

core/telemetry.py
  -> configures tracer/meter providers
  -> OTLP HTTP exporters
  -> FastAPI and HTTPX instrumentation
  -> helpers for trace id/span attributes

di/registrars/demo.py
  -> wires settings, skill loader, MCP factory, agent worker, service
```

### Data Flow

1. Client calls `POST /api/v1/demo/reserve-recommended-seat` with JSON body and optional propagation headers.
2. Demo route extracts or creates:
   - `traceparent`
   - `tracestate`
   - `correlation_id`
   - `request_id`
   - `workflow_id`
3. Route calls `DemoReservationService.reserve_recommended_seat(...)`.
4. Service invokes `DemoAgentWorker.run(...)`.
5. `load_context`:
   - loads static skills from markdown
   - connects to MCP servers or uses wrappers that connect lazily
   - lists tools and stores allowed metadata
6. `agent_reason`:
   - uses configured LLM when available
   - otherwise uses deterministic fallback sequence
7. `tool_call`:
   - invokes the selected allowlisted MCP tool
   - injects propagation headers and safe metadata
   - wraps the call in a manual span
8. `observe`:
   - normalizes the tool output
   - updates state fields such as `reservation_request_id` and `reservation_status`
   - logs `agent.tool_call.completed` or `agent.tool_call.failed`
9. The graph loops until success, rejected/failed status, dependency error, or max steps.
10. `finalize` returns a structured response DTO.

### Request/Trace Context

Create a typed context object:

```python
@dataclass(frozen=True)
class DemoTraceContext:
    traceparent: str | None
    tracestate: str | None
    correlation_id: str
    request_id: str
    workflow_id: str
```

Use this context explicitly in the demo service and MCP client. Do not rely only on ambient `contextvars`, because MCP propagation is a correctness requirement and should be visible in function signatures.

Enhance execution context separately so logs can also bind correlation/request IDs:

- Add optional `CORRELATION_ID`, `REQUEST_ID`, `TRACEPARENT`, and `TRACESTATE` contextvars.
- Preserve inbound `X-Request-Id`; generate UUID when missing.
- Preserve inbound `X-Correlation-Id`; default to request ID when missing.
- Keep JWT token behavior unchanged.

### Static Skills

Represent skills as markdown assets:

```text
llm_agent/agent_run_worker/demo/skills/reservation_demo_workflow/SKILL.md
llm_agent/agent_run_worker/demo/skills/observability_demo/SKILL.md
```

`llm_agent/agent_run_worker/demo/skill_loader.py` should expose:

```python
@dataclass(frozen=True)
class DemoSkill:
    name: str
    content: str

class DemoSkillLoader(Protocol):
    def load_skills(self) -> list[DemoSkill]: ...
```

Implementation should use `importlib.resources.files(...)` so skills are available from an installed wheel/container. Avoid filesystem paths relative to the working directory. Each `SKILL.md` must start with YAML frontmatter containing exactly `name` and `description`, followed by the markdown instructions used in the agent system prompt.

The loaded skill content becomes part of the agent context/system prompt. The deterministic planner should still work even if the LLM path is disabled.

### MCP Client Strategy

Use two explicit FastMCP clients rather than one multi-server config for the first implementation:

- It avoids server-name tool prefix confusion.
- It makes routing obvious: recommendation tools go to the recommendation/movie MCP service, movie reservation tools go to the movie MCP service.
- It makes request-scoped header propagation easier to reason about.

The wrapper should still call `list_tools()` and compare against the allowlist so the demo proves discovery. If a required tool is missing, fail early with a controlled dependency error.

Recommended interface:

```python
class DemoMcpToolClient(Protocol):
    async def list_available_tools(self, trace_context: DemoTraceContext) -> list[DemoToolMetadata]: ...
    async def call_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        trace_context: DemoTraceContext,
    ) -> DemoToolResult: ...
```

Implementation notes:

- Use `async with Client(url, timeout=settings.mcp_timeout_seconds, headers=...)` if the installed FastMCP version supports transport headers directly.
- If direct headers are not accepted by the constructor, use the documented transport configuration or underlying httpx transport configuration for headers.
- Keep an explicit mapping from tool name to MCP server URL/client.
- Enforce allowlist before calling MCP.
- Add per-call timeout with `asyncio.timeout(...)` if FastMCP timeout behavior is not sufficient.
- Normalize FastMCP result objects into simple DTOs before they enter the graph state.

### Agent Graph

State fields:

- `messages`
- `skills`
- `available_tools`
- `tool_results`
- `reservation_request_id`
- `reservation_status`
- `final_answer`
- `trace_context`
- `fault`
- `step`
- `next_tool_name`
- `next_tool_arguments`
- `workflow_id`
- `outcome`
- `error`

Graph behavior:

- `load_context`:
  - log `agent.workflow.started`
  - start span `agent.load_context`
  - load skills
  - discover MCP tools
- `agent_reason`:
  - start span `agent.reason`
  - log `agent.thought`
  - decide next tool or finalization
- `tool_call`:
  - start span `agent.tool_call`
  - log `agent.tool_call.started`
  - call MCP wrapper
- `observe`:
  - start span `agent.observe`
  - normalize/store result
  - log completed/failed event
- `finalize`:
  - start span `agent.finalize`
  - log `agent.workflow.completed` or `agent.workflow.failed`

Max steps:

- Default to `8`.
- Terminal statuses:
  - `confirmed`
  - `rejected`
  - `failed`
  - `dependency_failed`
  - `max_steps_exceeded`

### API Response Shape

Request DTO:

```json
{
  "movie_preference": "something exciting",
  "seat_preference": "aisle",
  "fault": "none"
}
```

Response DTO:

```json
{
  "workflow_id": "uuid",
  "outcome": "confirmed",
  "reservation_status": "confirmed",
  "reservation_request_id": "reservation-123",
  "movie": {
    "id": "movie-1",
    "title": "Example"
  },
  "screening": {
    "id": "screening-1"
  },
  "seat": {
    "id": "A1"
  },
  "tool_results": [
    {
      "tool_name": "recommendation_get_movies",
      "outcome": "succeeded"
    }
  ],
  "trace": {
    "trace_id": "otel-trace-id",
    "correlation_id": "demo-manual-001",
    "request_id": "demo-manual-001-request"
  }
}
```

For controlled dependency failure, return an error DTO:

```json
{
  "error": "demo_dependency_failed",
  "message": "Recommendation service failed",
  "workflow_id": "uuid",
  "trace": {
    "trace_id": "otel-trace-id",
    "correlation_id": "demo-manual-001",
    "request_id": "demo-manual-001-request"
  }
}
```

### Observability

Structured logs:

- `agent.workflow.started`
- `agent.thought`
- `agent.tool_call.started`
- `agent.tool_call.completed`
- `agent.tool_call.failed`
- `agent.workflow.completed`
- `agent.workflow.failed`

Every ReAct log includes:

- `service_name="movie-agent-worker"`
- `trace_id`
- `correlation_id`
- `request_id`
- `workflow_id`
- `step`
- `tool_name` when relevant
- `fault`
- `outcome`

Manual spans:

- `agent.workflow`
- `agent.load_context`
- `agent.reason`
- `agent.tool_call`
- `agent.observe`
- `agent.finalize`
- `mcp.tool.<tool_name>`

Span attributes:

- `demo.workflow_id`
- `demo.fault`
- `demo.outcome`
- `mcp.tool.name`
- `mcp.server.url`
- `correlation_id`
- `request_id`

Metrics:

- `agent_workflow_started_total`
- `agent_workflow_completed_total`
- `agent_workflow_failed_total`
- `agent_tool_call_total`
- `agent_tool_call_failed_total`
- `agent_workflow_duration_ms`
- `agent_tool_call_duration_ms`

### Control Plane Scope

The "control plane" for this demo is the request-time orchestration boundary that loads context, chooses tools, invokes MCP servers, and exposes observable workflow state. Missing parts to create:

- Demo route and DTOs.
- Demo service/use-case boundary.
- Static skill loader.
- MCP tool discovery/call wrapper.
- Agent graph worker.
- Telemetry helpers.
- Demo DI registrar and test fakes.
- Docker compose service and env config.

Do not add durable control-plane persistence unless a later demo needs querying historical workflows.

## 7. Alternatives Considered

### Alternative A: Explicit Two-Client MCP Wrapper

- Pros:
  - Simple routing from tool name to server.
  - Easier propagation of per-request headers.
  - Easier to fake in tests.
  - Matches the mission's reliability-first guidance.
- Cons:
  - Less elegant than dynamic multi-server tool mounting.
  - Requires maintaining a small tool allowlist and mapping.
- Decision:
  - Recommended for the first demo implementation.

### Alternative B: FastMCP Multi-Server Config with Prefixed Tools

- Pros:
  - Built-in support for multiple MCP servers.
  - Tool discovery and namespacing handled by FastMCP.
  - Could scale better if the demo adds many MCP services.
- Cons:
  - Prefixing can change tool names and complicate the required hardcoded sequence.
  - Per-request header propagation may be harder depending on FastMCP transport config.
  - More moving parts for a demo that needs predictable execution.
- Decision:
  - Defer until explicit two-client approach becomes painful.

### Alternative C: Pure FastAPI Orchestration Without LangGraph

- Pros:
  - Fewer dependencies.
  - Easier to debug.
  - Enough for a fixed reservation workflow.
- Cons:
  - Violates the mission requirement to use LangGraph.
  - Does not demonstrate an agent-like ReAct loop.
- Decision:
  - Reject.

### Alternative D: Persist Demo Workflows in Piccolo/Postgres

- Pros:
  - Enables run history and async polling.
  - More production-like control plane.
- Cons:
  - Adds migrations and data consistency concerns that are unnecessary for tonight's demo.
  - Increases blast radius in a repo with existing unrelated persistence work.
- Decision:
  - Reject for now. Keep the demo synchronous and in-memory per request.

## 8. API / Interface Changes

Public HTTP API:

- Add `GET /api/v1/demo/health`
  - `200 OK`
  - Response: `{"status": "ok", "service": "movie-agent-worker"}`
  - No authentication for demo.
- Add `POST /api/v1/demo/reserve-recommended-seat`
  - `200 OK` for confirmed/rejected business outcomes.
  - `422 Unprocessable Entity` for invalid `fault`.
  - `502 Bad Gateway` for MCP dependency failure.
  - `504 Gateway Timeout` for MCP timeout or max workflow timeout.

New DTO modules:

- `llm_agent/llm_agent/api/http/v1/dto/demo.py`
  - `DemoReservationRequestDto`
  - `DemoReservationResponseDto`
  - `DemoReservationErrorDto`
  - `DemoTraceDto`
  - nested movie/screening/seat/tool result DTOs as needed

New route module:

- `llm_agent/llm_agent/api/http/v1/routes/demo.py`
  - `demo_router = APIRouter()`
  - small `get_demo_reservation_service(...)` dependency using `svcs.fastapi.DepContainer`

New internal interfaces/types:

- `llm_agent/agent_run_worker/demo/config.py`
  - `DemoAgentSettings`
- `llm_agent/agent_run_worker/demo/trace_context.py`
  - `DemoTraceContext`
- `llm_agent/agent_run_worker/demo/skill_loader.py`
  - `DemoSkill`, `DemoSkillLoader`, `PackageDemoSkillLoader`
- `llm_agent/agent_run_worker/demo/mcp_client.py`
  - `DemoMcpToolClient`, `FastMcpDemoToolClient`, `DemoToolMetadata`, `DemoToolResult`
- `llm_agent/agent_run_worker/demo/agent_worker.py`
  - `DemoAgentWorker`, state type, deterministic planner
- `llm_agent/llm_agent/services/demo/reservation_service.py`
  - `DemoReservationService`

DI:

- Add `llm_agent/llm_agent/di/registrars/demo.py`.
- Add `DemoAgentRegistrar()` to `get_production_registrars()` and development/test provider as needed.

Configuration:

- Add environment-backed settings:
  - `MOVIE_RESERVATION_MCP_URL`
  - `AXUM_TOOLS_MCP_URL`
  - `DEMO_AGENT_MAX_STEPS`
  - `DEMO_MCP_TIMEOUT_SECONDS`
  - `OTEL_SERVICE_NAME`
  - optional model settings such as `DEMO_LLM_PROVIDER`, `DEMO_LLM_MODEL`, `OPENROUTER_API_KEY`, `OPENROUTER_ALLOWED_MODELS`, and `OPENROUTER_AUTO_COST_QUALITY_TRADEOFF`

## 9. Data Model / Persistence Changes

None.

The demo workflow is synchronous and per-request. No Piccolo tables or migrations are needed.

Rollback:

- Remove the demo router, registrar, dependencies, and compose service.
- No data rollback is required.

## 10. Security, Privacy, and Abuse Considerations

- Demo endpoints should be unauthenticated only for the demo branch/topology. Keep this localized by adding explicit public-path support to `AuthenticationMiddleware`; do not disable auth globally.
- Allowlist MCP tools. Do not call arbitrary discovered tools.
- Validate `fault` with a Pydantic enum/literal.
- Sanitize logs:
  - Log tool names and outcomes.
  - Do not log authorization headers, JWTs, API keys, raw `traceparent` if that becomes sensitive in the target environment, full request payloads, or full MCP responses.
- Propagation headers:
  - Forward only required tracing/correlation headers.
  - Do not forward inbound `Authorization` to MCP servers unless explicitly required later.
- Static skills:
  - Treat skill markdown as trusted repository code.
  - Do not support user-supplied skill paths or dynamic downloads.
- LLM path:
  - If a real LLM is configured, pass only the demo-safe prompt, skills, summarized tool metadata, and sanitized prior observations.
  - Do not send secrets or full internal headers to the model.
- MCP failure handling:
  - Convert network/protocol errors into controlled demo errors.
  - Avoid leaking internal stack traces to clients.
- Abuse:
  - Add small timeouts and max steps so the endpoint cannot loop indefinitely.
  - If exposed beyond local demo, add auth/rate limits before use.

## 11. Performance, Scalability, and Reliability Considerations

- The endpoint is synchronous and will hold one FastAPI worker until the workflow completes. This is acceptable for a local demo but not a production high-throughput design.
- Use bounded workflow steps, bounded MCP timeouts, and no unbounded fan-out.
- Per-request MCP clients are simple and reliable but add connection overhead. If this becomes visible, move to lifecycle-owned clients with request-specific headers supported by transport options.
- Slow fault path should remain observable and bounded by timeout.
- Dependency failure should produce:
  - clear response status/body
  - `agent.workflow.failed` log
  - failed span with exception/status
  - failure metric
- Tool result normalization prevents large MCP payloads from bloating graph state and logs.
- Keep metrics cardinality low:
  - tool name is acceptable
  - workflow ID should not be a metric label
  - raw error messages should not be metric labels
- OpenTelemetry exporter should fail soft. Telemetry export failure must not fail the reservation request.

## 12. Implementation Steps

1. Add dependencies
   - Change:
     - Add LangGraph, LangChain core, FastMCP, optional model provider, OTLP exporter, FastAPI instrumentation, and HTTPX instrumentation.
     - Update `uv.lock`.
   - Files/modules likely affected:
     - `llm_agent/pyproject.toml`
     - `llm_agent/uv.lock`
   - Notes:
     - Use `uv add ...` from `llm_agent/`.
     - Recommended packages:
       - `langgraph`
       - `langchain-core`
       - OpenRouter over the existing `httpx` dependency
       - `fastmcp`
       - `opentelemetry-exporter-otlp-proto-http`
       - `opentelemetry-instrumentation-fastapi`
       - `opentelemetry-instrumentation-httpx`
     - Use OpenRouter's OpenAI-compatible chat completion endpoint with configurable model selection.
   - Verification:
     - `cd llm_agent && uv run python -c "import langgraph, fastmcp; print('ok')"`

2. Implement telemetry setup
   - Change:
     - Replace the telemetry stub with SDK setup, OTLP HTTP trace/metric exporters, FastAPI instrumentation, HTTPX instrumentation, and helper functions.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/core/telemetry.py`
     - `llm_agent/llm_agent/core/log_config.py`
   - Notes:
     - Configure `Resource` from `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`.
     - Use `FastAPIInstrumentor.instrument_app(app, http_capture_headers_server_request=[...], http_capture_headers_sanitize_fields=[...])`.
     - Use `HTTPXClientInstrumentor().instrument()`.
     - Add helpers:
       - `get_current_trace_id() -> str | None`
       - `set_span_attributes_safe(...)`
       - `get_tracer(name: str)`
       - `get_meter(name: str)`
     - Make initialization idempotent for tests.
   - Verification:
     - Unit test helper formatting for trace ID.
     - Run app startup with no OTLP collector and confirm it does not crash.

3. Preserve request and correlation IDs
   - Change:
     - Extend execution context to preserve inbound request/correlation/trace headers and bind them to structlog contextvars.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/api/context/constants.py`
     - `llm_agent/llm_agent/api/context/request.py`
     - `llm_agent/llm_agent/infrastructure/execution_context/production.py`
     - `llm_agent/llm_agent/infrastructure/execution_context/fake.py`
     - `llm_agent/llm_agent/infrastructure/execution_context/request_id.py`
   - Notes:
     - Keep JWT behavior unchanged.
     - Generate full UUID request IDs instead of six-character suffixes for demo traceability.
     - Bind `correlation_id`, `request_id`, and, where useful, `traceparent`.
   - Verification:
     - Unit test middleware/enricher with inbound `X-Request-Id` and `X-Correlation-Id`.

4. Add explicit public-path support for demo health
   - Change:
     - Make `AuthenticationMiddleware` skip `/api/v1/demo/health`, and likely `/api/v1/demo/reserve-recommended-seat` for this local demo.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/api/http/middlewares/authentication.py`
   - Notes:
     - Prefer a tuple or settings-backed list of public prefixes.
     - Keep existing auth for `/api/v1/agent` and unrelated routes.
   - Verification:
     - API test confirms demo endpoints work without Authorization.
     - Existing agent route auth behavior is not accidentally weakened in production-style tests.

5. Add demo DTOs and API route
   - Change:
     - Add request/response DTOs and `demo_router`.
     - Include the router in `create_app(...)` with prefix `/api/v1/demo`.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/api/http/v1/dto/demo.py`
     - `llm_agent/llm_agent/api/http/v1/routes/demo.py`
     - `llm_agent/llm_agent/app.py`
   - Notes:
     - Keep route thin: extract headers, call `DemoReservationService`, map expected failures.
     - Use `response_model`, `summary`, `responses`.
     - Use `Literal["none", "slow-recommendation", "recommendation-error"]` or enum for `fault`.
   - Verification:
     - Route validation test for unsupported `fault`.
     - Health test returns `200`.

6. Add static skill markdown and loader
   - Change:
     - Add markdown skill files and package loader.
   - Files/modules likely affected:
     - `llm_agent/agent_run_worker/demo/__init__.py`
     - `llm_agent/agent_run_worker/demo/skill_loader.py`
     - `llm_agent/agent_run_worker/demo/skills/reservation_demo_workflow/SKILL.md`
     - `llm_agent/agent_run_worker/demo/skills/observability_demo/SKILL.md`
   - Notes:
     - Use `importlib.resources`.
     - Keep markdown content directive and concise.
     - Ensure package data is included by current Hatch build config; if needed, add Hatch package-data config.
   - Verification:
     - Unit test loads both skills from installed package path/import resources.

7. Add demo configuration
   - Change:
     - Add Pydantic settings for MCP URLs, timeouts, max steps, service name, and optional LLM model config.
   - Files/modules likely affected:
     - `llm_agent/agent_run_worker/demo/config.py`
     - `configuration/env_files/templates/local/local-development.env.template`
     - `configuration/env_files/templates/in-docker/local-development.env.template`
     - `configuration/env_files/templates/in-docker/local-production.env.template`
   - Notes:
     - Keep host/IDE and Docker values separate.
     - Fix stale `throttling_sequencer...` module paths in demo env files if those files are used by compose.
   - Verification:
     - Unit test default settings and env override behavior.

8. Add MCP client wrappers
   - Change:
     - Implement allowlisted FastMCP clients, discovery, calls, normalization, timeouts, and controlled exceptions.
   - Files/modules likely affected:
     - `llm_agent/agent_run_worker/demo/mcp_client.py`
     - `llm_agent/tests/fake_implementations/agent_run_worker/demo/mcp_client.py` or local test fakes
   - Notes:
     - Start with explicit clients per MCP URL.
     - Discover tools with `list_tools()`.
     - Verify required tool names are available.
     - Forward trace/correlation/request context.
     - Add manual spans around calls.
   - Verification:
     - Unit test required tool missing -> controlled dependency error.
     - Unit test header/context propagation to fake client.
     - Unit test tool allowlist rejects unknown tool.

9. Add deterministic planner
   - Change:
     - Implement fixed ReAct sequence and argument builder from previous tool results.
   - Files/modules likely affected:
     - `llm_agent/agent_run_worker/demo/agent_worker.py`
   - Notes:
     - Planner should not depend on LangGraph internals; make it directly unit-testable.
     - It should choose the first recommended movie, first screening, and first available seat.
     - It should stop on confirmed/rejected/failed.
   - Verification:
     - Unit test sequence:
       - recommendation
       - list screenings
       - request reservation
       - poll status
       - get result
     - Unit test max steps.

10. Add optional model-backed reasoner
   - Change:
     - Add a small model factory and model-backed `agent_reason` branch when provider config is present.
   - Files/modules likely affected:
     - `llm_agent/agent_run_worker/demo/model.py`
     - `llm_agent/agent_run_worker/demo/agent_worker.py`
   - Notes:
     - If no key is present, fallback planner is used.
     - Keep prompt construction sanitized and bounded.
     - Do not let provider import/config failure break deterministic fallback unless explicitly configured as required.
   - Verification:
     - Unit test no key -> deterministic planner.
     - Optional/manual test with provider key if available.

11. Build LangGraph agent worker
   - Change:
     - Create `StateGraph` with required nodes, conditional loop, and finalization.
   - Files/modules likely affected:
     - `llm_agent/agent_run_worker/demo/agent_worker.py`
   - Notes:
     - Follow LangGraph official `StateGraph` pattern: define state, add nodes, add edges, compile.
     - Wrap each node with manual OTel span/logging.
     - Keep state typed with `TypedDict` or dataclass-compatible structures.
   - Verification:
     - Unit test happy path with fake MCP client.
     - Unit test dependency failure path.
     - Unit test rejected/failed reservation terminal path.

12. Add demo reservation service
   - Change:
     - Add a service boundary that receives a typed request and returns a typed result.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/services/demo/__init__.py`
     - `llm_agent/llm_agent/services/demo/reservation_service.py`
   - Notes:
     - Service should not import FastAPI.
     - Service should be easy to construct with fake worker in tests.
   - Verification:
     - Unit test service maps worker result/failure correctly.

13. Wire DI registrar
   - Change:
     - Register settings, skill loader, MCP client factory/client, agent worker, and demo service.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/di/registrars/demo.py`
     - `llm_agent/llm_agent/di/app_registrar_providers.py`
     - `llm_agent/tests/fake_implementations/llm_agent/di/app_registrar_providers.py`
   - Notes:
     - Put request-visible services in `fastapi_lifespan_registrars`.
     - Keep registrar mechanical.
     - Add test override examples using `DependencyOverrideRegistrar`.
   - Verification:
     - Thin app test acquires service through route dependency.

14. Emit required structured ReAct logs
   - Change:
     - Add logging helpers or direct structured log calls in agent worker/MCP wrapper.
   - Files/modules likely affected:
     - `llm_agent/agent_run_worker/demo/agent_worker.py`
     - `llm_agent/agent_run_worker/demo/mcp_client.py`
     - `llm_agent/llm_agent/core/log_config.py`
   - Notes:
     - Ensure every required event includes the required fields.
     - Use `OTEL_SERVICE_NAME` or demo settings for `service_name`, default `movie-agent-worker`.
   - Verification:
     - Unit test with a structlog capture fixture or monkeypatched logger to assert event names and fields.

15. Dockerize the demo worker
   - Change:
     - Update compose with `movie-agent-worker` service on `127.0.0.1:8081:8081`.
     - Update Dockerfile exposure/healthcheck or make it port-env aware.
   - Files/modules likely affected:
     - `docker-compose.yml`
     - `llm_agent/Dockerfile`
     - `configuration/env_files/templates/in-docker/local-production.env.template`
   - Notes:
     - Compose service:
       - build context `./llm_agent`
       - target `prod`
       - container name `movie-agent-worker`
       - `UVICORN_PORT=8081` or `PORT=8081` after aligning config
       - OTel env from mission
       - MCP URL env from mission
       - labels `observability.logs: "true"`
       - `extra_hosts: ["host.docker.internal:host-gateway"]`
     - `UvicornServerConfig` currently uses `UVICORN_PORT`; either set that in compose or add support for `PORT` as an alias.
   - Verification:
     - `docker compose build movie-agent-worker`
     - `docker compose up movie-agent-worker`
     - `curl http://127.0.0.1:8081/api/v1/demo/health`

16. Add focused tests
   - Change:
     - Add unit and thin integration tests for planner, skills, MCP wrapper, service, and route.
   - Files/modules likely affected:
     - `llm_agent/tests/unit/demo/test_skills.py`
     - `llm_agent/tests/unit/demo/test_deterministic_planner.py`
     - `llm_agent/tests/unit/demo/test_mcp_client.py`
     - `llm_agent/tests/thin_integration/test_demo_reservation_route.py`
   - Notes:
     - Use fakes over mocks for MCP wrapper behavior.
     - Do not require real MCP servers in automated tests.
   - Verification:
     - `cd llm_agent && uv run pytest tests/unit/demo tests/thin_integration/test_demo_reservation_route.py`

17. Add manual demo verification docs
   - Change:
     - Document curl commands and expected log/span checks.
   - Files/modules likely affected:
     - `llm_agent/README.md` or `docs/knowledge/demo-multi-service-observability-agent-worker.md`
   - Notes:
     - Keep docs focused on running this demo.
   - Verification:
     - Follow the documented commands from a clean shell.

18. Run final checks
   - Change:
     - Run focused tests, lint, and container smoke checks.
   - Files/modules likely affected:
     - None, unless fixes are needed.
   - Notes:
     - Use the narrowest tests while iterating, then broader check before handoff.
   - Verification:
     - `cd llm_agent && uv run pytest`
     - `cd llm_agent && uv run ruff check .`
     - `docker compose build movie-agent-worker`
     - `docker compose up movie-agent-worker`
     - manual curl commands below

## 13. Testing Strategy

Unit tests:

- Static skill loader:
  - loads `reservation_demo_workflow`
  - loads `observability_demo`
  - fails clearly when a required skill file is missing
- Deterministic planner:
  - emits required sequence
  - builds tool arguments from previous results
  - stops at confirmed/rejected/failed
  - stops at max steps
- MCP client wrapper:
  - discovers required tools
  - fails if required tools are missing
  - rejects non-allowlisted tool calls
  - propagates `traceparent`, `tracestate`, `X-Correlation-Id`, and `X-Request-Id`
  - maps timeout/network errors to controlled exceptions
- Telemetry helpers:
  - trace ID formatter returns expected value
  - span attributes are set safely
  - setup is idempotent
- Demo service:
  - maps worker success to result
  - maps dependency failure to service exception/result

Thin integration tests:

- FastAPI route with fake MCP/worker:
  - health endpoint returns `200` without auth
  - reserve endpoint validates `fault`
  - happy path returns expected DTO
  - dependency error returns `502`
  - timeout path returns `504`
  - inbound correlation/request IDs appear in response trace and log fields
- DI test:
  - app composition includes demo service
  - tests can override demo MCP/worker via registrar

Manual demo verification:

```sh
curl -sS http://127.0.0.1:8081/api/v1/demo/health

curl -sS http://127.0.0.1:8081/api/v1/demo/reserve-recommended-seat \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-manual-001" \
  -H "X-Request-Id: demo-manual-001-request" \
  -d '{"movie_preference":"exciting","seat_preference":"aisle","fault":"none"}'

curl -sS http://127.0.0.1:8081/api/v1/demo/reserve-recommended-seat \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-manual-slow-001" \
  -H "X-Request-Id: demo-manual-slow-001-request" \
  -d '{"movie_preference":"exciting","seat_preference":"aisle","fault":"slow-recommendation"}'

curl -sS http://127.0.0.1:8081/api/v1/demo/reserve-recommended-seat \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-manual-error-001" \
  -H "X-Request-Id: demo-manual-error-001-request" \
  -d '{"movie_preference":"exciting","seat_preference":"aisle","fault":"recommendation-error"}'
```

Observability checks:

- Logs contain all required `agent.*` events.
- Logs include `service_name=movie-agent-worker`.
- Trace waterfall shows:
  - inbound FastAPI span
  - `agent.workflow`
  - LangGraph node spans
  - MCP tool spans
  - HTTPX outbound spans
- Slow path visibly increases recommendation/tool span duration.
- Error path shows failed workflow log/span and controlled client response.

## 14. Rollout / Migration Plan

This is a demo branch rollout.

Phase 1: Local code path

- Add dependencies, demo modules, tests, and local env config.
- Run route tests with fake MCP clients.

Phase 2: Container smoke

- Build `movie-agent-worker`.
- Start service without MCP dependencies.
- Verify `/api/v1/demo/health`.
- Verify dependency failure is controlled when MCP is unavailable.

Phase 3: Full demo stack

- Start MCP services and observability collector/Grafana/Loki stack.
- Set `MOVIE_RESERVATION_MCP_URL` and `AXUM_TOOLS_MCP_URL` for Docker network.
- Run happy, slow, and error curl calls.
- Confirm logs/traces/metrics.

Rollback:

- Remove `movie-agent-worker` compose service or stop it.
- Revert demo registrar/router inclusion if it interferes with existing service.
- No database rollback.

Feature flag:

- Optional: add `DEMO_AGENT_ENABLED=true` and return `404`/do not include router when false.
- Not required for local demo, but useful if this branch is merged into a broader scaffold.

## 15. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---:|---:|---|
| FastMCP header propagation API differs from expectation | High | Medium | Verify installed docs/API during implementation; isolate propagation in `FastMcpDemoToolClient`; fallback to transport config or metadata argument |
| MCP tool schemas differ from mission assumptions | High | Medium | Use `list_tools()` schema metadata and per-tool adapters; fail startup/request clearly if required tools are missing |
| Existing auth middleware blocks demo curl calls | Medium | High | Add explicit public path prefixes for `/api/v1/demo/*` in demo branch |
| Existing env files contain stale module paths | Medium | High | Fix demo-used env files and prefer compose inline env for critical settings |
| OTel exporter errors break app startup/request handling | High | Low | Configure exporters defensively; telemetry must fail soft |
| LangGraph or provider dependency changes API | Medium | Medium | Use official current docs during implementation; keep deterministic planner decoupled and directly testable |
| LLM path makes demo nondeterministic | Medium | Medium | Deterministic fallback remains default without key; tests target fallback path |
| Logs leak MCP payloads or headers | High | Medium | Log tool name/outcome only; add explicit sanitization and avoid raw body logging |
| Synchronous workflow blocks workers during slow fault demo | Low | High | Bound timeout/max steps; acceptable for local demo; document as non-production |
| Docker hostnames differ between host and compose | Medium | Medium | Separate local/IDE and Docker env values; include `extra_hosts` for host gateway |

## 16. Done Criteria

- `movie-agent-worker` starts on port `8081`.
- `GET /api/v1/demo/health` returns `200`.
- `POST /api/v1/demo/reserve-recommended-seat` accepts the required body and headers.
- Static markdown skills are loaded into the agent context/system prompt.
- Agent discovers required tools from MCP servers.
- Agent calls both MCP servers through allowlisted wrappers.
- LangGraph ReAct-style loop runs through the reservation workflow.
- Deterministic fallback completes the happy path without a real LLM key.
- Optional LLM branch is available when configured and does not block fallback.
- Trace/correlation/request headers propagate to MCP calls.
- Required JSON log events are emitted with required fields.
- FastAPI inbound, HTTPX outbound, graph node, and MCP tool spans appear in OpenTelemetry.
- Metrics are emitted for workflow/tool counts and durations.
- `fault=slow-recommendation` produces visible slow spans/logs.
- `fault=recommendation-error` produces controlled failure response/logs/spans.
- Focused automated tests pass.
- Docker compose smoke path works.

## 17. Review Checklist

- [x] Requirements are explicit
- [x] Non-goals are explicit
- [x] Existing code conventions were checked
- [x] Alternatives were considered
- [x] Security implications were reviewed
- [x] Scalability and reliability implications were reviewed
- [x] Testing strategy is complete
- [x] Rollout and rollback are defined
- [x] Implementation steps are ordered and concrete

## 18. Handoff Prompt for Implementation Agent

Copy/paste this prompt into a coding agent:

```text
Implement the plan in docs/plans/demo-multi-service-observability-agent-worker.md.

Constraints:
- Stay within the demo scope. Do not finish unrelated throttle/game/navigation work.
- Follow this repo's FastAPI + svcs composition pattern.
- Keep routes thin and put control-plane orchestration in `llm_agent/llm_agent/services/demo` and worker runtime logic in `llm_agent/agent_run_worker/demo`.
- Keep the demo workflow synchronous and per-request; do not add persistence or migrations.
- Use static `SKILL.md` files packaged under `llm_agent/agent_run_worker/demo/skills`.
- Use explicit two-client FastMCP wrappers with an allowlist for the required tools.
- The deterministic fallback planner must work without a real LLM API key.
- Preserve and propagate traceparent, tracestate, X-Correlation-Id, and X-Request-Id to MCP calls.
- Add OpenTelemetry FastAPI, HTTPX, manual graph-node, and MCP tool instrumentation.
- Emit required structured ReAct logs and do not log secrets/raw tokens/full payloads.
- Add focused unit and thin integration tests with fakes; do not require real MCP servers in automated tests.
- Update Docker compose/env so movie-agent-worker runs on 8081 with required OTel/MCP env vars.
- If implementation reality differs from the plan, update the plan or ask before changing scope.

Relevant files/modules:
- llm_agent/pyproject.toml
- llm_agent/uv.lock
- llm_agent/llm_agent/app.py
- llm_agent/llm_agent/core/telemetry.py
- llm_agent/llm_agent/core/log_config.py
- llm_agent/llm_agent/api/http/middlewares/authentication.py
- llm_agent/llm_agent/infrastructure/execution_context/production.py
- llm_agent/llm_agent/api/http/v1/routes/demo.py
- llm_agent/llm_agent/api/http/v1/dto/demo.py
- llm_agent/agent_run_worker/demo/
- llm_agent/llm_agent/services/demo/
- llm_agent/llm_agent/di/registrars/demo.py
- llm_agent/llm_agent/di/app_registrar_providers.py
- llm_agent/tests/unit/demo/
- llm_agent/tests/thin_integration/test_demo_reservation_route.py
- docker-compose.yml
- llm_agent/Dockerfile
- configuration/env_files/templates/in-docker/local-production.env.template
- configuration/env_files/templates/in-docker/local-development.env.template
- configuration/env_files/templates/local/local-development.env.template

Expected verification commands:
- cd llm_agent && uv run pytest tests/unit/demo tests/thin_integration/test_demo_reservation_route.py
- cd llm_agent && uv run pytest
- cd llm_agent && uv run ruff check .
- docker compose build movie-agent-worker
- docker compose up movie-agent-worker
- curl -sS http://127.0.0.1:8081/api/v1/demo/health
- curl -sS http://127.0.0.1:8081/api/v1/demo/reserve-recommended-seat \
    -H "Content-Type: application/json" \
    -H "X-Correlation-Id: demo-manual-001" \
    -H "X-Request-Id: demo-manual-001-request" \
    -d '{"movie_preference":"exciting","seat_preference":"aisle","fault":"none"}'
```
