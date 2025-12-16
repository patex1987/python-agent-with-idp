import asyncio
import random
from typing import Protocol

import structlog

from llm_agent.services.agent.queue import JobQueue
from llm_agent.services.agent.store import JobStore

logger = structlog.get_logger(__name__)

class Consumer(Protocol):
    async def consume_and_execute_loop(self): ...

    async def shutdown_execution(self): ...


class InMemoryConsumer(Consumer):
    def __init__(self, job_store: JobStore, job_queue: JobQueue, worker_id: str):
        self.job_store = job_store
        self.job_queue = job_queue
        self._execution_allowed = True
        self.worker_id = "worker-1"

    async def consume_and_execute_loop(self):
        """
        TODO: [CRITICAL] move the state transition to JobStore (or elsewhere),
            and validate if the given change is allowed
        TODO: refactor into smaller unit. Use the following at least:
            - consumer loop
            - job executor
            - execution policy
        TODO: implement the notifier and hook into relevant events
        """
        while self._execution_allowed:
            job_id = await self.job_queue.claim_next(self.worker_id)
            if not job_id:
                await asyncio.sleep(0.1)
                continue

            logger.info(f"{self.worker_id}: executing job", job_id=job_id)
            await self.job_store.set_running(job_id, self.worker_id)
            # await notifier.publish(JobEvent(job_id, "started", {}))

            try:
                for i in range(5):
                    logger.info(f"{self.worker_id}: Running job step", job_id=job_id, step=i)
                    step_execution_time = random.randint(2, 7)
                    await asyncio.sleep(step_execution_time)
                    await self.job_store.set_progress(job_id, i / 5, {"step": i})
                    # await notifier.publish(JobEvent(job_id, "progress", {"step": i}))

                logger.info(f"{self.worker_id}: job done", job_id=job_id)
                await self.job_store.set_succeeded(job_id, {"ok": True})
                # await notifier.publish(JobEvent(job_id, "succeeded", {}))
            except Exception as e:
                logger.error(f"{self.worker_id}: job failed", job_id=job_id, error=str(e))
                await self.job_store.set_failed(job_id, str(e))
                # await notifier.publish(JobEvent(job_id, "failed", {"error": str(e)}))

    async def shutdown_execution(self):
        self._execution_allowed = False
