import fastapi
import svcs.fastapi
from fastapi import APIRouter, Query
from uuid import UUID

from llm_agent.api.http.v1.dto.agent_prompt import AgentPromptDto
from llm_agent.api.http.v1.dto.cancelled_run import CancelRunResponseDto
from llm_agent.api.http.v1.dto.created_run import CreatedRunDto
from llm_agent.api.http.v1.dto.run import RunDto
from llm_agent.api.http.v1.dto.run_event import RunEventDto
from llm_agent.api.http.v1.mappers.created_run import CreatedRunV1Mapper
from llm_agent.api.http.v1.mappers.run import RunV1Mapper
from llm_agent.api.http.v1.mappers.run_event import RunEventV1Mapper
from llm_agent.domain.agent.runs.exception import RunNotFoundError
from llm_agent.services.agent.orchestrator import BackendRunOrchestrationService
from llm_agent.services.agent.queue import RunSignalQueue
from llm_agent.services.agent.store import RunIntakeStore

agent_router = APIRouter()


def get_run_service(services: svcs.fastapi.DepContainer) -> BackendRunOrchestrationService:
    """
    Get the run orchestration service.
    """
    return BackendRunOrchestrationService(
        run_store=services.get(RunIntakeStore),
        run_signal_queue=services.get(RunSignalQueue),
    )


@agent_router.post(
    "/runs",
    response_model=CreatedRunDto,
    summary="Create an agent run",
    description="Creates a new agent run to execute the provided prompt.",
)
async def create_agent_run(
    agent_prompt: AgentPromptDto,
    request: fastapi.Request,
    run_service: BackendRunOrchestrationService = fastapi.Depends(get_run_service),
):
    created_run_status = await run_service.create_run(agent_prompt.prompt)
    created_run_dto = CreatedRunV1Mapper.to_dto(created_run_status)
    return created_run_dto


@agent_router.get(
    "/runs/{run_id}",
    response_model=RunDto,
    summary="Get run state",
    description=(
        "Retrieves the complete state of an agent run"
        "Possible status values: CREATED, ENQUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED, TIMED_OUT, RETRYING. "
        "Returns 404 if the run is not found."
    ),
    responses={
        200: {
            "description": "Run state retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "status": "RUNNING",
                        "result": None,
                        "error": None,
                        "cancel_requested": False,
                    }
                }
            },
        },
        404: {
            "description": "Run not found",
            "content": {
                "application/json": {"example": {"detail": "Run 123e4567-e89b-12d3-a456-426614174000 not found"}}
            },
        },
    },
)
async def get_agent_run(
    run_id: UUID,
    request: fastapi.Request,
    run_service: BackendRunOrchestrationService = fastapi.Depends(get_run_service),
):
    try:
        run_status = await run_service.get_run(run_id)
        return RunV1Mapper.to_dto(run_status)
    except RunNotFoundError as exc:
        raise fastapi.HTTPException(status_code=404, detail=str(exc))


@agent_router.post(
    "/runs/{run_id}/cancel",
    response_model=CancelRunResponseDto,
    summary="Request run cancellation",
    description=(
        "Requests cancellation of a run. This sets the cancellation intent flag. "
        "If a worker is executing the run, it will discover the cancellation at the next "
        "checkpoint and exit cooperatively.\n\n"
        "Important: Termination is not immediate. There are two sources of delay:\n"
        "1. Detection delay: Up to the heartbeat interval (default: 5 seconds) before "
        "the worker detects the cancellation signal\n"
        "2. Checkpoint delay: The worker will complete the current step/operation "
        "before stopping execution\n\n"
        "This checkpoint-based approach ensures operations complete atomically and "
        "prevents partial state or data corruption. Execution stops gracefully after "
        "finishing the next checkpoint, not in the middle of an operation."
    ),
    responses={
        200: {
            "description": "Cancellation requested or run already terminal",
            "content": {
                "application/json": {
                    "examples": {
                        "cancel_requested": {
                            "value": {
                                "run_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "cancel_requested",
                                "message": "Run cancellation requested",
                            }
                        },
                        "already_terminal": {
                            "value": {
                                "run_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "already_terminal",
                                "message": "Run already in terminal state",
                            }
                        },
                    }
                }
            },
        },
        404: {"description": "Run not found"},
    },
)
async def cancel_agent_run(
    run_id: UUID,
    request: fastapi.Request,
    run_service: BackendRunOrchestrationService = fastapi.Depends(get_run_service),
):
    try:
        was_cancelled = await run_service.cancel_run(run_id)
        if was_cancelled:
            return CancelRunResponseDto(
                run_id=run_id,
                status="cancel_requested",
                message="Run cancellation requested",
            )
        else:
            return CancelRunResponseDto(
                run_id=run_id,
                status="already_terminal",
                message="Run already in terminal state or cancel is requested",
            )
    except RunNotFoundError as exc:
        raise fastapi.HTTPException(status_code=404, detail=str(exc))


@agent_router.get(
    "/runs/{run_id}/events",
    response_model=list[RunEventDto],
    summary="List run events",
    description=(
        "Retrieves the event logs for a run, optionally filtered by sequence number. "
        "Events are returned in chronological order (by sequence number). "
        "Use the 'after' query parameter to paginate through events.\n\n"
        "Returns 404 if the run is not found. Returns 400 if event log is not available."
    ),
    responses={
        200: {
            "description": "Run events retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "sequence_nr": 1,
                            "event_type": "created",
                            "payload": {"user_id": "user123"},
                            "timestamp_utc": "2026-01-09T12:34:56Z",
                        },
                        {
                            "sequence_nr": 2,
                            "event_type": "enqueued",
                            "payload": {},
                            "timestamp_utc": "2026-01-09T12:34:57Z",
                        },
                    ]
                }
            },
        },
        400: {
            "description": "Event log not available",
            "content": {"application/json": {"example": {"detail": "Event log is not available"}}},
        },
        404: {
            "description": "Run not found",
            "content": {
                "application/json": {"example": {"detail": "Run 123e4567-e89b-12d3-a456-426614174000 not found"}}
            },
        },
    },
)
async def get_agent_run_events(
    run_id: UUID,
    after: int | None = Query(None, description="Return events after this sequence number"),
    request: fastapi.Request = None,
    run_service: BackendRunOrchestrationService = fastapi.Depends(get_run_service),
):
    try:
        await run_service.get_run(run_id)
        events = await run_service.get_events(run_id, after_sequence=after)
        return [RunEventV1Mapper.to_dto(event) for event in events]
    except RunNotFoundError as exc:
        raise fastapi.HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc))
