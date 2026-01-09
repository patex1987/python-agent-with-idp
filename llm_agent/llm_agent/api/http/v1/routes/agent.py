import fastapi
import svcs.fastapi
from fastapi import APIRouter, Query
from uuid import UUID

from llm_agent.api.http.v1.dto.agent_prompt import AgentPromptDto
from llm_agent.api.http.v1.dto.cancelled_job import CancelJobResponseDto
from llm_agent.api.http.v1.dto.created_job import CreatedJobDto
from llm_agent.api.http.v1.dto.job import JobDto
from llm_agent.api.http.v1.dto.job_event import JobEventDto
from llm_agent.api.http.v1.mappers.created_job import CreatedJobV1Mapper
from llm_agent.api.http.v1.mappers.job import JobV1Mapper
from llm_agent.api.http.v1.mappers.job_event import JobEventV1Mapper
from llm_agent.domain.agent.jobs.exception import JobNotFoundError
from llm_agent.services.agent.orchestrator import BackendJobOrchestrationService
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobIntakeStore

agent_router = APIRouter()


def get_job_service(services: svcs.fastapi.DepContainer) -> BackendJobOrchestrationService:
    """
    Get the job orchestration service.
    """
    return BackendJobOrchestrationService(
        job_store=services.get(JobIntakeStore),
        job_signal_queue=services.get(JobSignalQueue),
    )


@agent_router.post(
    "/jobs",
    response_model=CreatedJobDto,
    summary="Create an agent job",
    description="Creates a new agent job to execute the provided prompt.",
)
async def create_agent_job(
    agent_prompt: AgentPromptDto,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    created_job_status = await job_service.create_job(agent_prompt.prompt)
    created_job_dto = CreatedJobV1Mapper.to_dto(created_job_status)
    return created_job_dto


@agent_router.get(
    "/jobs/{job_id}",
    response_model=JobDto,
    summary="Get job state",
    description=(
        "Retrieves the complete state of an agent job"
        "Possible status values: CREATED, ENQUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED, TIMED_OUT, RETRYING. "
        "Returns 404 if the job is not found."
    ),
    responses={
        200: {
            "description": "Job state retrieved successfully",
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
            "description": "Job not found",
            "content": {
                "application/json": {"example": {"detail": "Job 123e4567-e89b-12d3-a456-426614174000 not found"}}
            },
        },
    },
)
async def get_agent_job(
    job_id: UUID,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    try:
        job_status = await job_service.get_job(job_id)
        return JobV1Mapper.to_dto(job_status)
    except JobNotFoundError as exc:
        raise fastapi.HTTPException(status_code=404, detail=str(exc))


@agent_router.post(
    "/jobs/{job_id}/cancel",
    response_model=CancelJobResponseDto,
    summary="Request job cancellation",
    description=(
        "Requests cancellation of a job. This sets the cancellation intent flag. "
        "If a worker is executing the job, it will discover the cancellation at the next "
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
            "description": "Cancellation requested or job already terminal",
            "content": {
                "application/json": {
                    "examples": {
                        "cancel_requested": {
                            "value": {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "cancel_requested",
                                "message": "Job cancellation requested",
                            }
                        },
                        "already_terminal": {
                            "value": {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "already_terminal",
                                "message": "Job already in terminal state",
                            }
                        },
                    }
                }
            },
        },
        404: {"description": "Job not found"},
    },
)
async def cancel_agent_job(
    job_id: UUID,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    try:
        was_cancelled = await job_service.cancel_job(job_id)
        if was_cancelled:
            return CancelJobResponseDto(
                job_id=job_id,
                status="cancel_requested",
                message="Job cancellation requested",
            )
        else:
            return CancelJobResponseDto(
                job_id=job_id,
                status="already_terminal",
                message="Job already in terminal state or cancel is requested",
            )
    except JobNotFoundError as exc:
        raise fastapi.HTTPException(status_code=404, detail=str(exc))


@agent_router.get(
    "/jobs/{job_id}/events",
    response_model=list[JobEventDto],
    summary="List job events",
    description=(
        "Retrieves the event logs for a job, optionally filtered by sequence number. "
        "Events are returned in chronological order (by sequence number). "
        "Use the 'after' query parameter to paginate through events.\n\n"
        "Returns 404 if the job is not found. Returns 400 if event log is not available."
    ),
    responses={
        200: {
            "description": "Job events retrieved successfully",
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
            "description": "Job not found",
            "content": {
                "application/json": {"example": {"detail": "Job 123e4567-e89b-12d3-a456-426614174000 not found"}}
            },
        },
    },
)
async def get_agent_job_events(
    job_id: UUID,
    after: int | None = Query(None, description="Return events after this sequence number"),
    request: fastapi.Request = None,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    try:
        await job_service.get_job(job_id)
        events = await job_service.get_events(job_id, after_sequence=after)
        return [JobEventV1Mapper.to_dto(event) for event in events]
    except JobNotFoundError as exc:
        raise fastapi.HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc))
