import logging
import uuid

import fastapi
import svcs.fastapi
from fastapi import APIRouter
from pydantic import BaseModel

from llm_agent.domain.agent.jobs.entities import JobRequest, EnqueuedJob, JobStatus
from llm_agent.infrastructure.agent.in_memory.store import InMemoryJobStore
from llm_agent.services.agent.store import JobStore

agent_router = APIRouter()


class AgentPromptDto(BaseModel):
    prompt: str
    history: list[str]


class JobService:

    # TODO: this is just a stupid POC, so storing as a class var
    job_store = InMemoryJobStore()

    async def create_job(self, prompt: str) -> EnqueuedJob:
        job_request = JobRequest(
            prompt=prompt,
            history=[],
            user_id="hardcoded_user_later_from_context",
        )
        enqueued_job = await self.job_store.create_job(
            job_request=job_request,
        )
        return enqueued_job

    async def get_job(self, job_id: str) -> JobStatus:
        job_status = await self.job_store.get_status(job_id=uuid.UUID(job_id))
        return job_status


def get_job_service(services: svcs.fastapi.DepContainer) -> JobService:
    # return services.get(JobService)

    return JobService()


@agent_router.post(
    "/create-job",
    response_model=EnqueuedJob,
    summary="Compute throttle steps for first player/enemy unit",
)
async def create_agent_job(
    agent_prompt: AgentPromptDto,
    request: fastapi.Request,
    job_service: JobService = fastapi.Depends(get_job_service),
):
    enqueued_job = await job_service.create_job(agent_prompt.prompt)
    return enqueued_job

class JobExecutionStatus(BaseModel):
    status: str


@agent_router.get(
    "/get-job-status/{job_id}",
    response_model=JobExecutionStatus,
    summary="Check the status of the agent job",
)
async def get_agent_job(
    job_id: str,
    request: fastapi.Request,
    job_service: JobService = fastapi.Depends(get_job_service),
):
    job_status = await job_service.get_job(job_id)
    return job_status
