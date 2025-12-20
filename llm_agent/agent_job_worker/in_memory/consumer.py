import asyncio
import random
from typing import Protocol
from uuid import UUID

import structlog

from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobProcessingStore

logger = structlog.get_logger(__name__)


class Consumer(Protocol):
    async def consume_and_execute_loop(self): ...

    async def shutdown_execution(self): ...


class InMemoryConsumer(Consumer):
    def __init__(self, job_store: JobProcessingStore, job_signal_queue: JobSignalQueue, worker_id: str):
        self.job_store = job_store
        self.job_signal_queue = job_signal_queue
        self._execution_allowed = True
        self.worker_id = worker_id

    async def consume_and_execute_loop(self):
        """
        TODO: refactor into smaller unit. Use the following at least:
            - consumer loop
            - job executor
            - execution policy
        TODO: implement the notifier and hook into relevant events
        TODO: add a concurrent health checker, so it's literally just
            checking if the worker is running
        """
        while self._execution_allowed:
            await self.job_signal_queue.wait()
            enqueued_job = await self.job_store.claim_job(self.worker_id)
            if not enqueued_job:
                continue

            job_id = enqueued_job.id
            logger.info(f"{self.worker_id}: executing job", job_id=job_id)
            # await notifier.publish(JobEvent(job_id, "started", {}))

            try:
                await execute_agent_job(job_id, self.worker_id, self.job_store)

                logger.info(f"{self.worker_id}: job done", job_id=job_id)
                await self.job_store.set_succeeded(job_id, {"ok": True})
                # await notifier.publish(JobEvent(job_id, "succeeded", {}))
            except Exception as e:
                logger.error(f"{self.worker_id}: job failed", job_id=job_id, error=str(e))
                await self.job_store.set_failed(job_id, str(e))
                # await notifier.publish(JobEvent(job_id, "failed", {"error": str(e)}))

    async def shutdown_execution(self):
        self._execution_allowed = False


async def execute_agent_job(job_id: UUID, worker_id: str, job_store: JobProcessingStore):
    """
    TODO: just a poc, move to a dedicated configurable class

    :param job_id:
    :param worker_id:
    :param job_store:
    :return:
    """
    for i in range(5):
        logger.info(f"{worker_id}: Running job step", job_id=job_id, step=i)
        step_execution_time = random.randint(0, 4)
        await asyncio.sleep(step_execution_time)
        await job_store.heartbeat(job_id, worker_id)
        # await self.job_store.set_progress(job_id, i / 5, {"step": i})
        # await notifier.publish(JobEvent(job_id, "progress", {"step": i}))
