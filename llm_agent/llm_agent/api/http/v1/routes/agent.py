
import fastapi
import svcs.fastapi
from fastapi import APIRouter
from pydantic import BaseModel

from llm_agent.api.http.v1.dto.agent_prompt import AgentPromptDto
from llm_agent.api.http.v1.dto.created_job import CreatedJobDto
from llm_agent.api.http.v1.mappers.created_job import CreatedJobV1Mapper
from llm_agent.services.agent.orchestrator import BackendJobOrchestrationService
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
    summary="Compute throttle steps for first player/enemy unit",
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
)
async def get_agent_job(
    job_id: str,
    request: fastapi.Request,
    job_service: BackendJobOrchestrationService = fastapi.Depends(get_job_service),
):
    job_status = await job_service.get_job(job_id)
    return JobExecutionStatusDto(status=job_status.status.name)
