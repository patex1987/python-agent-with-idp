from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from agent_run_worker.demo.trace_context import DemoTraceContext

DemoFault = Literal["none", "slow-recommendation", "recommendation-error"]


@dataclass(frozen=True)
class DemoReservationRequest:
    movie_preference: str
    seat_preference: str
    fault: DemoFault
    trace_context: DemoTraceContext


@dataclass(frozen=True)
class DemoToolMetadata:
    name: str
    server_name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class DemoToolResult:
    tool_name: str
    outcome: str
    payload: Any = None
    error: str | None = None


@dataclass(frozen=True)
class DemoReservationResult:
    workflow_id: str
    outcome: str
    reservation_status: str | None
    reservation_request_id: str | None
    final_answer: str
    trace_context: DemoTraceContext
    movie: dict[str, Any] | None = None
    screening: dict[str, Any] | None = None
    seat: dict[str, Any] | None = None
    tool_results: list[DemoToolResult] = field(default_factory=list)
    error: str | None = None


class DemoWorkflowError(RuntimeError):
    def __init__(self, result: DemoReservationResult) -> None:
        super().__init__(result.error or result.final_answer)
        self.result = result


class DemoDependencyError(DemoWorkflowError):
    pass


class DemoWorkflowTimeoutError(DemoWorkflowError):
    pass
