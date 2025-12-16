import fastapi
import svcs.fastapi
from fastapi import APIRouter
from pydantic import BaseModel

from llm_agent.api.http.v1.dto.agent_prompt import AgentPromptDto
from llm_agent.domain.agent.jobs.entities import EnqueuedJob
from llm_agent.services.agent.orchestrator import BackendJobOrchestrationService
from llm_agent.services.agent.queue import JobQueue
from llm_agent.services.agent.store import JobStore

agent_router = APIRouter()


def get_job_service(services: svcs.fastapi.DepContainer) -> BackendJobOrchestrationService:
    return BackendJobOrchestrationService(
        job_store=services.get(JobStore),
        job_queue=services.get(JobQueue),
    )


@agent_router.post(
    "/create-job",
    response_model=EnqueuedJob,
    summary="Compute throttle steps for first player/enemy unit",
)
async def create_agent_job(
    agent_prompt: AgentPromptDto,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    enqueued_job = await job_service.create_job(agent_prompt.prompt)
    return enqueued_job


class JobExecutionStatusDto(BaseModel):
    status: str


@agent_router.get(
    "/get-job-status/{job_id}",
    response_model=JobExecutionStatusDto,
    summary="Check the status of the agent job",
)
async def get_agent_job(
    job_id: str,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    job_status = await job_service.get_job(job_id)
    return JobExecutionStatusDto(status=job_status.status.name)

