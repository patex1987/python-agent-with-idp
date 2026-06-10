from __future__ import annotations

import fastapi
import svcs.fastapi
from fastapi.responses import JSONResponse
from starlette import status

from llm_agent.api.http.v1.dto.demo import (
    DemoReservationErrorDto,
    DemoReservationRequestDto,
    DemoReservationResponseDto,
    DemoToolResultDto,
    DemoTraceDto,
)
from agent_run_worker.demo.trace_context import DemoTraceContext
from agent_run_worker.demo.types import (
    DemoDependencyError,
    DemoReservationRequest,
    DemoReservationResult,
    DemoWorkflowTimeoutError,
)
from llm_agent.core.telemetry import get_current_trace_id, get_current_traceparent
from llm_agent.services.demo.reservation_service import DemoReservationService

demo_router = fastapi.APIRouter()


def get_demo_reservation_service(services: svcs.fastapi.DepContainer) -> DemoReservationService:
    return services.get(DemoReservationService)


@demo_router.get(
    "/health",
    summary="Demo agent health",
)
async def demo_health() -> dict[str, str]:
    return {"status": "ok", "service": "movie-agent-worker"}


@demo_router.post(
    "/reserve-recommended-seat",
    response_model=DemoReservationResponseDto,
    summary="Reserve a recommended movie seat",
    responses={
        status.HTTP_502_BAD_GATEWAY: {"model": DemoReservationErrorDto, "description": "MCP dependency failed"},
        status.HTTP_504_GATEWAY_TIMEOUT: {"model": DemoReservationErrorDto, "description": "Demo workflow timed out"},
    },
)
async def reserve_recommended_seat(
    payload: DemoReservationRequestDto,
    request: fastapi.Request,
    reservation_service: DemoReservationService = fastapi.Depends(get_demo_reservation_service),
) -> DemoReservationResponseDto | JSONResponse:
    trace_context = DemoTraceContext.from_headers(
        headers=request.headers,
        scope_state=request.scope.get("state", {}),
        current_traceparent=get_current_traceparent(),
    )
    service_request = DemoReservationRequest(
        movie_preference=payload.movie_preference,
        seat_preference=payload.seat_preference,
        fault=payload.fault,
        trace_context=trace_context,
    )

    try:
        result = await reservation_service.reserve_recommended_seat(service_request)
    except DemoDependencyError as exc:
        return _error_response("demo_dependency_failed", exc.result, status.HTTP_502_BAD_GATEWAY)
    except DemoWorkflowTimeoutError as exc:
        return _error_response("demo_workflow_timeout", exc.result, status.HTTP_504_GATEWAY_TIMEOUT)

    return _to_response_dto(result)


def _error_response(error_code: str, result: DemoReservationResult, status_code: int) -> JSONResponse:
    error_dto = DemoReservationErrorDto(
        error=error_code,
        message=result.error or result.final_answer,
        workflow_id=result.workflow_id,
        trace=DemoTraceDto(**result.trace_context.to_response_trace(get_current_trace_id())),
    )
    return JSONResponse(status_code=status_code, content=error_dto.model_dump())


def _to_response_dto(result: DemoReservationResult) -> DemoReservationResponseDto:
    return DemoReservationResponseDto(
        workflow_id=result.workflow_id,
        outcome=result.outcome,
        reservation_status=result.reservation_status,
        reservation_request_id=result.reservation_request_id,
        final_answer=result.final_answer,
        movie=result.movie,
        screening=result.screening,
        seat=result.seat,
        tool_results=[
            DemoToolResultDto(tool_name=tool_result.tool_name, outcome=tool_result.outcome)
            for tool_result in result.tool_results
        ],
        trace=DemoTraceDto(**result.trace_context.to_response_trace(get_current_trace_id())),
    )
