from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from agent_run_worker.demo.agent_worker import DemoAgentWorker, DeterministicReservationPlanner
from agent_run_worker.demo.config import DemoAgentSettings
from agent_run_worker.demo.skill_loader import DemoSkill
from agent_run_worker.demo.trace_context import DemoTraceContext
from agent_run_worker.demo.types import DemoReservationRequest, DemoToolMetadata, DemoToolResult


def test_deterministic_planner_sequence():
    planner = DeterministicReservationPlanner(recommendation_limit=5)
    trace_context = _trace_context()
    state = {
        "messages": [],
        "skills": [],
        "available_tools": [],
        "tool_results": [],
        "reservation_request_id": None,
        "reservation_status": None,
        "final_answer": None,
        "trace_context": trace_context,
        "fault": "none",
        "workflow_id": trace_context.workflow_id,
        "step": 0,
        "started_at": 0.0,
        "movie_preference": "exciting",
        "seat_preference": "aisle",
        "outcome": None,
        "error": None,
        "selected_movie": None,
        "selected_screening": None,
        "selected_seat": None,
        "next_tool_name": None,
        "next_tool_arguments": None,
    }

    assert planner.next_action(state)[0] == "recommendation_get_movies"

    state["tool_results"] = [DemoToolResult("recommendation_get_movies", "succeeded", {})]
    state["selected_movie"] = {"movie_reservation_movie_id": "movie-1"}
    tool_name, arguments = planner.next_action(state)
    assert tool_name == "movie_list_screenings"
    assert arguments == {"movie_id": "movie-1"}

    state["tool_results"].append(DemoToolResult("movie_list_screenings", "succeeded", []))
    state["selected_screening"] = {"id": "screening-1"}
    state["selected_seat"] = {"id": "seat-1"}
    tool_name, arguments = planner.next_action(state)
    assert tool_name == "movie_request_reservation"
    assert arguments == {"screening_id": "screening-1", "seat_ids": ["seat-1"]}

    state["tool_results"].append(DemoToolResult("movie_request_reservation", "succeeded", {}))
    state["reservation_request_id"] = "request-1"
    assert planner.next_action(state)[0] == "movie_get_reservation_status"

    state["tool_results"].append(DemoToolResult("movie_get_reservation_status", "succeeded", {}))
    assert planner.next_action(state)[0] == "movie_get_reservation_result"


@pytest.mark.asyncio
async def test_agent_worker_happy_path_uses_required_tool_sequence():
    fake_mcp = FakeMcpClient()
    worker = DemoAgentWorker(
        settings=DemoAgentSettings(demo_llm_provider="none"),
        skill_loader=FakeSkillLoader(),
        mcp_client=fake_mcp,
    )

    result = await worker.run(
        DemoReservationRequest(
            movie_preference="exciting",
            seat_preference="aisle",
            fault="none",
            trace_context=_trace_context(),
        )
    )

    assert result.outcome == "confirmed"
    assert result.reservation_request_id == "request-1"
    assert [call.tool_name for call in fake_mcp.calls] == [
        "recommendation_get_movies",
        "movie_list_screenings",
        "movie_request_reservation",
        "movie_get_reservation_status",
        "movie_get_reservation_result",
    ]
    assert fake_mcp.calls[0].arguments["correlation_id"] == "corr-1"
    assert fake_mcp.calls[0].arguments["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_agent_worker_dependency_failure_is_terminal():
    fake_mcp = FakeMcpClient(fail_tool="recommendation_get_movies")
    worker = DemoAgentWorker(
        settings=DemoAgentSettings(demo_llm_provider="none"),
        skill_loader=FakeSkillLoader(),
        mcp_client=fake_mcp,
    )

    result = await worker.run(
        DemoReservationRequest(
            movie_preference="exciting",
            seat_preference="aisle",
            fault="recommendation-error",
            trace_context=_trace_context(),
        )
    )

    assert result.outcome == "dependency_failed"
    assert result.error == "forced failure"
    assert [call.tool_name for call in fake_mcp.calls] == ["recommendation_get_movies"]


def _trace_context() -> DemoTraceContext:
    return DemoTraceContext(
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        correlation_id="corr-1",
        request_id="req-1",
        workflow_id="workflow-1",
    )


class FakeSkillLoader:
    def load_skills(self) -> list[DemoSkill]:
        return [
            DemoSkill("reservation-demo-workflow", "reserve a seat", "pick a recommendation"),
            DemoSkill("observability-demo", "preserve ids", "preserve ids"),
        ]


@dataclass(frozen=True)
class ObservedCall:
    tool_name: str
    arguments: dict[str, Any]


class FakeMcpClient:
    def __init__(self, fail_tool: str | None = None) -> None:
        self.fail_tool = fail_tool
        self.calls: list[ObservedCall] = []

    async def list_available_tools(self, trace_context: DemoTraceContext) -> list[DemoToolMetadata]:
        return [
            DemoToolMetadata("recommendation_get_movies", "axum_tools"),
            DemoToolMetadata("movie_list_screenings", "movie_reservation"),
            DemoToolMetadata("movie_request_reservation", "movie_reservation"),
            DemoToolMetadata("movie_get_reservation_status", "movie_reservation"),
            DemoToolMetadata("movie_get_reservation_result", "movie_reservation"),
        ]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        trace_context: DemoTraceContext,
        *,
        fault: str,
    ) -> DemoToolResult:
        merged_arguments = {**arguments, **trace_context.to_tool_arguments(fault=fault)}
        self.calls.append(ObservedCall(tool_name, merged_arguments))
        if tool_name == self.fail_tool:
            return DemoToolResult(tool_name, "failed", error="forced failure")

        payload_by_tool = {
            "recommendation_get_movies": {
                "ok": True,
                "recommendations": [{"id": "rec-1", "movie_reservation_movie_id": "movie-1"}],
            },
            "movie_list_screenings": [
                {
                    "id": "screening-1",
                    "movieId": "movie-1",
                    "seats": [{"id": "seat-1", "row": "A", "number": 1}],
                }
            ],
            "movie_request_reservation": {"id": "request-1", "status": "pending"},
            "movie_get_reservation_status": {"id": "request-1", "status": "confirmed"},
            "movie_get_reservation_result": {
                "id": "reservation-1",
                "reservationRequestId": "request-1",
                "seatIds": ["seat-1"],
            },
        }
        return DemoToolResult(tool_name, "succeeded", payload_by_tool[tool_name])
