from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, NotRequired, TypedDict

import structlog
from langgraph.graph import END, START, StateGraph
from opentelemetry.trace import Status, StatusCode

from agent_run_worker.demo.config import DemoAgentSettings
from agent_run_worker.demo.mcp_client import DemoMcpToolClient
from agent_run_worker.demo.model_client import DemoModelClient
from agent_run_worker.demo.skill_loader import DemoSkill, DemoSkillLoader
from agent_run_worker.demo.trace_context import DemoTraceContext
from agent_run_worker.demo.types import DemoReservationRequest, DemoReservationResult, DemoToolMetadata, DemoToolResult
from llm_agent.core.telemetry import get_current_trace_id, get_meter, get_tracer, set_span_attributes

logger = structlog.get_logger(__name__)

TERMINAL_OUTCOMES = {"confirmed", "rejected", "failed", "dependency_failed", "max_steps_exceeded"}

meter = get_meter(__name__)
workflow_started_counter = meter.create_counter("agent_workflow_started_total")
workflow_completed_counter = meter.create_counter("agent_workflow_completed_total")
workflow_failed_counter = meter.create_counter("agent_workflow_failed_total")
tool_call_counter = meter.create_counter("agent_tool_call_total")
tool_call_failed_counter = meter.create_counter("agent_tool_call_failed_total")
workflow_duration_histogram = meter.create_histogram("agent_workflow_duration_ms")
tool_call_duration_histogram = meter.create_histogram("agent_tool_call_duration_ms")


class DemoAgentState(TypedDict):
    messages: list[dict[str, str]]
    skills: list[DemoSkill]
    available_tools: list[DemoToolMetadata]
    tool_results: list[DemoToolResult]
    reservation_request_id: str | None
    reservation_status: str | None
    final_answer: str | None
    trace_context: DemoTraceContext
    fault: str
    workflow_id: str
    step: int
    started_at: float
    movie_preference: str
    seat_preference: str
    outcome: str | None
    error: str | None
    selected_movie: dict[str, Any] | None
    selected_screening: dict[str, Any] | None
    selected_seat: dict[str, Any] | None
    next_tool_name: NotRequired[str | None]
    next_tool_arguments: NotRequired[dict[str, Any] | None]


class DeterministicReservationPlanner:
    def __init__(self, recommendation_limit: int) -> None:
        self._recommendation_limit = recommendation_limit

    def next_action(self, state: DemoAgentState) -> tuple[str | None, dict[str, Any]]:
        completed_tools = [result.tool_name for result in state["tool_results"] if result.outcome == "succeeded"]

        if "recommendation_get_movies" not in completed_tools:
            return "recommendation_get_movies", {
                "limit": self._recommendation_limit,
                "preference": state["movie_preference"],
                "fault": state["fault"],
            }

        if "movie_list_screenings" not in completed_tools:
            movie = state["selected_movie"] or {}
            return "movie_list_screenings", {"movie_id": preferred_movie_id(movie)}

        if "movie_request_reservation" not in completed_tools:
            screening = state["selected_screening"] or {}
            seat = state["selected_seat"] or {}
            return "movie_request_reservation", {
                "screening_id": screening.get("id"),
                "seat_ids": [seat.get("id")],
            }

        if "movie_get_reservation_status" not in completed_tools:
            return "movie_get_reservation_status", {
                "reservation_request_id": state["reservation_request_id"],
            }

        if "movie_get_reservation_result" not in completed_tools:
            return "movie_get_reservation_result", {
                "reservation_request_id": state["reservation_request_id"],
            }

        return None, {}


class DemoAgentWorker:
    def __init__(
        self,
        *,
        settings: DemoAgentSettings,
        skill_loader: DemoSkillLoader,
        mcp_client: DemoMcpToolClient,
        model_client: DemoModelClient | None = None,
    ) -> None:
        self._settings = settings
        self._skill_loader = skill_loader
        self._mcp_client = mcp_client
        self._planner = DeterministicReservationPlanner(settings.demo_recommendation_limit)
        self._tracer = get_tracer(__name__)
        self._model_client = model_client
        self._graph = self._build_graph()

    async def run(self, request: DemoReservationRequest) -> DemoReservationResult:
        workflow_started_counter.add(1, {"fault": request.fault})
        initial_state: DemoAgentState = {
            "messages": [],
            "skills": [],
            "available_tools": [],
            "tool_results": [],
            "reservation_request_id": None,
            "reservation_status": None,
            "final_answer": None,
            "trace_context": request.trace_context,
            "fault": request.fault,
            "workflow_id": request.trace_context.workflow_id,
            "step": 0,
            "started_at": time.perf_counter(),
            "movie_preference": request.movie_preference,
            "seat_preference": request.seat_preference,
            "outcome": None,
            "error": None,
            "selected_movie": None,
            "selected_screening": None,
            "selected_seat": None,
            "next_tool_name": None,
            "next_tool_arguments": None,
        }

        with self._tracer.start_as_current_span("agent.workflow") as span:
            set_span_attributes(
                span,
                {
                    "demo.workflow_id": request.trace_context.workflow_id,
                    "demo.fault": request.fault,
                    "correlation_id": request.trace_context.correlation_id,
                    "request_id": request.trace_context.request_id,
                },
            )
            final_state = await self._graph.ainvoke(initial_state)
            if final_state.get("outcome") in {"dependency_failed", "max_steps_exceeded", "failed"}:
                span.set_status(Status(StatusCode.ERROR, final_state.get("error") or "Workflow failed"))

        return self._to_result(final_state)

    def _build_graph(self):
        graph = StateGraph(DemoAgentState)
        graph.add_node("load_context", self._load_context)
        graph.add_node("agent_reason", self._agent_reason)
        graph.add_node("tool_call", self._tool_call)
        graph.add_node("observe", self._observe)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "load_context")
        graph.add_edge("load_context", "agent_reason")
        graph.add_conditional_edges(
            "agent_reason",
            self._route_after_reason,
            {"tool_call": "tool_call", "finalize": "finalize"},
        )
        graph.add_edge("tool_call", "observe")
        graph.add_conditional_edges(
            "observe",
            self._route_after_observe,
            {"agent_reason": "agent_reason", "finalize": "finalize"},
        )
        graph.add_edge("finalize", END)
        return graph.compile()

    async def _load_context(self, state: DemoAgentState) -> dict[str, Any]:
        trace_context = state["trace_context"]
        with self._tracer.start_as_current_span("agent.load_context") as span:
            self._set_state_span_attributes(span, state)
            self._log_event("agent.workflow.started", state, outcome="started")
            try:
                skills = self._skill_loader.load_skills()
                available_tools = await self._mcp_client.list_available_tools(trace_context)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                return {
                    "outcome": "dependency_failed",
                    "error": str(exc),
                    "final_answer": "The reservation workflow could not load required MCP tools.",
                }

        return {
            "skills": skills,
            "available_tools": available_tools,
            "messages": [
                {
                    "role": "system",
                    "content": "\n\n".join(format_skill_for_prompt(skill) for skill in skills),
                }
            ],
        }

    async def _agent_reason(self, state: DemoAgentState) -> dict[str, Any]:
        with self._tracer.start_as_current_span("agent.reason") as span:
            self._set_state_span_attributes(span, state)

            if state.get("outcome") in TERMINAL_OUTCOMES:
                return {"next_tool_name": None, "next_tool_arguments": None}

            if state["step"] >= self._settings.demo_agent_max_steps:
                return {
                    "outcome": "max_steps_exceeded",
                    "error": "Demo workflow exceeded its maximum step count.",
                    "next_tool_name": None,
                    "next_tool_arguments": None,
                    "final_answer": "The reservation workflow timed out before reaching a terminal state.",
                }

            tool_name, arguments = await self._next_action(state)
            thought = f"Next action: {tool_name}" if tool_name else "No more tool actions are required."
            self._log_event(
                "agent.thought",
                state,
                outcome="planned" if tool_name else "ready_to_finalize",
                tool_name=tool_name,
                thought=thought,
            )

            return {
                "next_tool_name": tool_name,
                "next_tool_arguments": arguments,
                "messages": [*state["messages"], {"role": "assistant", "content": thought}],
            }

    async def _tool_call(self, state: DemoAgentState) -> dict[str, Any]:
        tool_name = state.get("next_tool_name")
        arguments = state.get("next_tool_arguments") or {}
        if not tool_name:
            return {}

        started = time.perf_counter()
        self._log_event("agent.tool_call.started", state, outcome="started", tool_name=tool_name)
        tool_call_counter.add(1, {"tool_name": tool_name, "fault": state["fault"]})

        with self._tracer.start_as_current_span("agent.tool_call") as span:
            self._set_state_span_attributes(span, state, tool_name=tool_name)
            result = await self._mcp_client.call_tool(
                tool_name,
                arguments,
                state["trace_context"],
                fault=state["fault"],
            )

            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            tool_call_duration_histogram.record(duration_ms, {"tool_name": tool_name, "fault": state["fault"]})
            if result.outcome != "succeeded":
                tool_call_failed_counter.add(1, {"tool_name": tool_name, "fault": state["fault"]})
                span.set_status(Status(StatusCode.ERROR, result.error or result.outcome))

        next_state: dict[str, Any] = {
            "step": state["step"] + 1,
            "tool_results": [*state["tool_results"], result],
            "next_tool_name": None,
            "next_tool_arguments": None,
        }
        if result.outcome != "succeeded":
            next_state.update(
                {
                    "outcome": "dependency_failed",
                    "error": result.error or f"Tool {tool_name} failed",
                    "final_answer": f"The reservation workflow failed while calling {tool_name}.",
                }
            )
        return next_state

    async def _observe(self, state: DemoAgentState) -> dict[str, Any]:
        with self._tracer.start_as_current_span("agent.observe") as span:
            self._set_state_span_attributes(span, state)
            latest = state["tool_results"][-1] if state["tool_results"] else None
            if latest is None:
                return {}

            if latest.outcome != "succeeded":
                self._log_event(
                    "agent.tool_call.failed",
                    state,
                    outcome=latest.outcome,
                    tool_name=latest.tool_name,
                    error=latest.error,
                )
                return {}

            observed_state = self._observe_tool_result(state, latest)
            outcome = observed_state.get("outcome") or "succeeded"
            self._log_event(
                "agent.tool_call.completed",
                state,
                outcome=outcome,
                tool_name=latest.tool_name,
            )
            return observed_state

    async def _finalize(self, state: DemoAgentState) -> dict[str, Any]:
        duration_ms = round((time.perf_counter() - state["started_at"]) * 1000, 3)
        outcome = state.get("outcome") or infer_success_outcome(state)
        final_answer = state.get("final_answer") or build_final_answer(outcome)
        workflow_duration_histogram.record(duration_ms, {"fault": state["fault"], "outcome": outcome})

        event_name = (
            "agent.workflow.completed" if outcome in {"confirmed", "rejected", "succeeded"} else "agent.workflow.failed"
        )
        if event_name == "agent.workflow.completed":
            workflow_completed_counter.add(1, {"fault": state["fault"], "outcome": outcome})
        else:
            workflow_failed_counter.add(1, {"fault": state["fault"], "outcome": outcome})

        with self._tracer.start_as_current_span("agent.finalize") as span:
            self._set_state_span_attributes(span, state)
            set_span_attributes(span, {"demo.outcome": outcome, "demo.workflow_duration_ms": duration_ms})
            if event_name.endswith("failed"):
                span.set_status(Status(StatusCode.ERROR, state.get("error") or outcome))
            self._log_event(event_name, state, outcome=outcome, duration_ms=duration_ms)

        return {
            "outcome": outcome,
            "final_answer": final_answer,
        }

    def _observe_tool_result(self, state: DemoAgentState, result: DemoToolResult) -> dict[str, Any]:
        payload = result.payload

        if result.tool_name == "recommendation_get_movies":
            if isinstance(payload, dict) and payload.get("ok") is False:
                return {
                    "outcome": "dependency_failed",
                    "error": str(payload.get("error") or "Recommendation dependency failed."),
                    "final_answer": "The recommendation dependency failed.",
                }

            movie = first_recommendation(payload)
            if movie is None:
                return {
                    "outcome": "failed",
                    "error": "Recommendation tool returned no movies.",
                    "final_answer": "No movie recommendations were available.",
                }
            return {"selected_movie": movie}

        if result.tool_name == "movie_list_screenings":
            screening = first_screening_with_seat(payload)
            if screening is None:
                return {
                    "outcome": "failed",
                    "error": "No screenings with seats were available.",
                    "final_answer": "No available screening seats were found.",
                }
            seat = first_seat(screening)
            return {"selected_screening": screening, "selected_seat": seat}

        if result.tool_name == "movie_request_reservation":
            request_id = value_by_keys(payload, "id", "reservation_request_id", "reservationRequestId")
            status = normalize_status(value_by_keys(payload, "status"))
            return {"reservation_request_id": request_id, "reservation_status": status}

        if result.tool_name == "movie_get_reservation_status":
            status = normalize_status(value_by_keys(payload, "status"))
            if status in {"rejected", "failed"}:
                return {
                    "reservation_status": status,
                    "outcome": status,
                    "final_answer": f"The reservation request was {status}.",
                }
            return {"reservation_status": status}

        if result.tool_name == "movie_get_reservation_result":
            if payload is None:
                return {
                    "outcome": state.get("reservation_status") or "failed",
                    "final_answer": "No reservation result was available.",
                }
            return {
                "outcome": "confirmed",
                "reservation_status": "confirmed",
                "final_answer": "Reserved a recommended screening.",
            }

        return {}

    async def _next_action(self, state: DemoAgentState) -> tuple[str | None, dict[str, Any]]:
        fallback_action = self._planner.next_action(state)
        if self._model_client is None:
            return fallback_action

        try:
            model_action = await self._next_action_with_model(state)
        except Exception as exc:
            logger.warning(
                "agent.llm_reasoning.failed",
                workflow_id=state["workflow_id"],
                correlation_id=state["trace_context"].correlation_id,
                request_id=state["trace_context"].request_id,
                error=str(exc),
            )
            return fallback_action

        if model_action[0] is None:
            return fallback_action
        return model_action

    async def _next_action_with_model(self, state: DemoAgentState) -> tuple[str | None, dict[str, Any]]:
        if self._model_client is None:
            return None, {}

        allowed_tool, fallback_arguments = self._planner.next_action(state)
        if allowed_tool is None:
            return None, {}

        system_content = "\n\n".join(format_skill_for_prompt(skill) for skill in state["skills"])
        user_content = (
            "Choose the next tool for the demo reservation workflow. "
            f"The deterministic safe next tool is {allowed_tool}. "
            "Return only that tool unless the workflow is already complete."
        )
        response = await self._model_client.complete(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            trace_context=state["trace_context"],
            workflow_id=state["workflow_id"],
        )
        if allowed_tool in response.content:
            return allowed_tool, fallback_arguments
        return allowed_tool, fallback_arguments

    @staticmethod
    def _route_after_reason(state: DemoAgentState) -> str:
        if state.get("outcome") in TERMINAL_OUTCOMES:
            return "finalize"
        if not state.get("next_tool_name"):
            return "finalize"
        return "tool_call"

    @staticmethod
    def _route_after_observe(state: DemoAgentState) -> str:
        if state.get("outcome") in TERMINAL_OUTCOMES:
            return "finalize"
        return "agent_reason"

    def _set_state_span_attributes(self, span: Any, state: DemoAgentState, *, tool_name: str | None = None) -> None:
        set_span_attributes(
            span,
            {
                "demo.workflow_id": state["workflow_id"],
                "demo.fault": state["fault"],
                "demo.step": state["step"],
                "demo.outcome": state.get("outcome"),
                "mcp.tool.name": tool_name,
                "correlation_id": state["trace_context"].correlation_id,
                "request_id": state["trace_context"].request_id,
            },
        )

    def _log_event(self, event_name: str, state: DemoAgentState, **fields: Any) -> None:
        trace_context = state["trace_context"]
        logger.info(
            event_name,
            service_name=self._settings.service_name,
            trace_id=get_current_trace_id() or trace_context.trace_id,
            correlation_id=trace_context.correlation_id,
            request_id=trace_context.request_id,
            workflow_id=state["workflow_id"],
            step=state["step"],
            fault=state["fault"],
            **fields,
        )

    @staticmethod
    def _to_result(state: DemoAgentState) -> DemoReservationResult:
        outcome = state.get("outcome") or infer_success_outcome(state)
        return DemoReservationResult(
            workflow_id=state["workflow_id"],
            outcome=outcome,
            reservation_status=state.get("reservation_status"),
            reservation_request_id=state.get("reservation_request_id"),
            final_answer=state.get("final_answer") or build_final_answer(outcome),
            trace_context=state["trace_context"],
            movie=state.get("selected_movie"),
            screening=state.get("selected_screening"),
            seat=state.get("selected_seat"),
            tool_results=state.get("tool_results", []),
            error=state.get("error"),
        )


def first_recommendation(payload: Any) -> dict[str, Any] | None:
    recommendations = payload.get("recommendations") if isinstance(payload, dict) else payload
    if not isinstance(recommendations, list) or not recommendations:
        return None
    first = recommendations[0]
    return first if isinstance(first, dict) else None


def first_screening_with_seat(payload: Any) -> dict[str, Any] | None:
    screenings = payload.get("screenings") if isinstance(payload, dict) else payload
    if not isinstance(screenings, list):
        return None

    for screening in screenings:
        if isinstance(screening, dict) and first_seat(screening) is not None:
            return screening
    return None


def first_seat(screening: Mapping[str, Any]) -> dict[str, Any] | None:
    seats = screening.get("seats")
    if not isinstance(seats, list) or not seats:
        return None

    for seat in seats:
        if isinstance(seat, dict) and seat.get("isReserved") is not True:
            return seat

    return None


def preferred_movie_id(movie: Mapping[str, Any]) -> str | None:
    return value_by_keys(movie, "movie_reservation_movie_id", "movieReservationMovieId", "movie_id", "movieId", "id")


def value_by_keys(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, Mapping):
        return None
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def normalize_status(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).lower()


def infer_success_outcome(state: DemoAgentState) -> str:
    if state.get("reservation_status") in {"confirmed", "succeeded"}:
        return "confirmed"
    if state.get("reservation_status") in {"rejected", "failed"}:
        return state["reservation_status"] or "failed"
    if any(
        result.tool_name == "movie_get_reservation_result" and result.outcome == "succeeded"
        for result in state["tool_results"]
    ):
        return "confirmed"
    return state.get("reservation_status") or "succeeded"


def build_final_answer(outcome: str) -> str:
    if outcome == "confirmed":
        return "Reserved a recommended screening."
    if outcome == "rejected":
        return "The reservation request was rejected."
    if outcome == "max_steps_exceeded":
        return "The reservation workflow timed out before completion."
    if outcome == "dependency_failed":
        return "A dependency failed during the reservation workflow."
    return "The reservation workflow completed."


def format_skill_for_prompt(skill: DemoSkill) -> str:
    return f"# Skill: {skill.name}\n\nDescription: {skill.description}\n\n{skill.content}"
