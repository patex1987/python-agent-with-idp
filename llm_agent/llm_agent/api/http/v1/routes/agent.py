import fastapi
import svcs.fastapi
from fastapi import APIRouter
from pydantic import BaseModel

from llm_agent.api.http.v1.dto.agent_prompt import AgentPromptDto
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
