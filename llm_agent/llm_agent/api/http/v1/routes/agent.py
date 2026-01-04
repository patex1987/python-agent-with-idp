import fastapi
import svcs.fastapi
from fastapi import APIRouter
from pydantic import BaseModel

from llm_agent.api.http.v1.dto.agent_prompt import AgentPromptDto
from llm_agent.api.http.v1.dto.cancelled_job import CancelJobResponseDto
from llm_agent.api.http.v1.dto.created_job import CreatedJobDto
from llm_agent.api.http.v1.mappers.created_job import CreatedJobV1Mapper
from llm_agent.services.agent.orchestrator import BackendJobOrchestrationService
from llm_agent.domain.agent.jobs.exception import JobNotFoundError
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobIntakeStore

agent_router = APIRouter()


def get_job_service(services: svcs.fastapi.DepContainer) -> BackendJobOrchestrationService:
    return BackendJobOrchestrationService(
        job_store=services.get(JobIntakeStore),
        job_signal_queue=services.get(JobSignalQueue),
    )


@agent_router.post(
    "/create-job",
    response_model=CreatedJobDto,
    summary="Post an agent job executing the provided prompt",
)
async def create_agent_job(
    agent_prompt: AgentPromptDto,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    created_job_status = await job_service.create_job(agent_prompt.prompt)
    created_job_dto = CreatedJobV1Mapper.to_dto(created_job_status)
    return created_job_dto


class JobExecutionStatusDto(BaseModel):
    status: str


@agent_router.get(
    "/get-job-status/{job_id}",
    response_model=JobExecutionStatusDto,
    summary="Check the status of the agent job",
    description=(
        "Retrieves the current status of an agent job by its ID. "
        "Possible status values: llm_agent.domain.agent.jobs.status_code.JobStatusCode"
        "Returns 404 if the job is not found."
    ),
    responses={
        200: {
            "description": "Job status retrieved successfully",
            "content": {"application/json": {"example": {"status": "RUNNING"}}},
        },
        404: {
            "description": "Job not found",
            "content": {
                "application/json": {"example": {"detail": "Job 123e4567-e89b-12d3-a456-426614174000 not found"}}
            },
        },
    },
)
async def get_agent_job_status(
    job_id: str,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    try:
        job_status = await job_service.get_job(job_id)
        return JobExecutionStatusDto(status=job_status.status.name)
    except JobNotFoundError as exc:
        raise fastapi.HTTPException(status_code=404, detail=str(exc))


@agent_router.post(
    "/jobs/{job_id}/cancel",
    response_model=CancelJobResponseDto,
    summary="Cancel a running agent job",
    description=(
        "Requests cancellation of a job. The job will be marked as CANCELLED "
        "in the store. If a worker is executing the job, it will discover "
        "the cancellation at the next checkpoint and exit cooperatively.\n\n"
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
                        "cancelled": {
                            "value": {"job_id": "...", "status": "cancelled", "message": "Job cancellation requested"}
                        },
                        "already_terminal": {
                            "value": {
                                "job_id": "...",
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
    job_id: str,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    try:
        was_cancelled = await job_service.cancel_job(job_id)
        if was_cancelled:
            return CancelJobResponseDto(
                job_id=job_id,
                status="cancelled",
                message="Job cancellation requested",
            )
        else:
            return CancelJobResponseDto(
                job_id=job_id,
                status="already_terminal",
                message="Job already in terminal state",
            )
    except JobNotFoundError as exc:
        raise fastapi.HTTPException(status_code=404, detail=str(exc))
