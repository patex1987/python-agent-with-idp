import asyncio
import random
from typing import Protocol
from uuid import UUID

import structlog

from llm_agent.services.agent.store import JobProcessingStore

logger = structlog.get_logger(__name__)


class AgentJobExecutor(Protocol):
    async def execute(self, job_id: UUID, worker_id: str, job_store: JobProcessingStore):
        """
        Contract for executing agent jobs by the consumer

        :param job_id:
        :param worker_id:
        :param job_store:
        :return:
        """
        ...


class RandomSleepJobExecutor(AgentJobExecutor):
    async def execute(self, job_id: UUID, worker_id: str, job_store: JobProcessingStore):
        """
        TODO: just a poc, move to a dedicated configurable class

        :param job_id:
        :param worker_id:
        :param job_store:
        :return:
        """
        for i in range(5):
            logger.info(f"{worker_id}: Running job step", job_id=job_id, step=i)
            step_execution_time = random.randint(0, 8)
            await asyncio.sleep(step_execution_time)
            await job_store.heartbeat(job_id, worker_id)
            # await self.job_store.set_progress(job_id, i / 5, {"step": i})
            # await notifier.publish(JobEvent(job_id, "progress", {"step": i}))


class DummyJobExecutor(AgentJobExecutor):
    async def execute(self, job_id: UUID, worker_id: str, job_store: JobProcessingStore):
        """
        TODO: just a poc, move to a dedicated configurable class

        :param job_id:
        :param worker_id:
        :param job_store:
        :return:
        """
        logger.info(f"{worker_id}: Running job step", job_id=job_id)
        await asyncio.sleep(0.2)
        await job_store.heartbeat(job_id, worker_id)
