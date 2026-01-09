import asyncio
import uuid

import structlog

from agent_job_worker.domain.exception import JobLeaseLostError
from llm_agent.domain.agent.jobs.execution_context import JobExecutionContext
from llm_agent.domain.agent.jobs.status_code import JobStatusCode
from llm_agent.services.agent.store import JobProcessingStore

logger = structlog.get_logger(__name__)


class JobLeaseScope:
    """
    Maintains job liveness while a worker is executing a claimed job.

    Responsibilities:
    - periodically renew the job lease via heartbeats
    - ensure the job is released if execution stops
    - scope liveness strictly to the execution lifetime

    Note: Do NOT add business timeouts here, that should be handled by
        the agent.
    """

    def __init__(
        self,
        worker_id: str,
        job_id: uuid.UUID,
        job_store: JobProcessingStore,
        job_execution_context: JobExecutionContext,
        heartbeat_interval_seconds: int = 5,
    ):
        self.worker_id = worker_id
        self.job_id = job_id
        self.job_store = job_store
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self._execution_ctx: JobExecutionContext = job_execution_context
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    async def __aenter__(self):
        self._running = True
        self._heartbeat_task = asyncio.create_task(self.heartbeat_loop(self.job_id, self._execution_ctx))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def heartbeat_loop(self, job_id: uuid.UUID, job_execution_ctx: JobExecutionContext):
        """
        Periodically check the liveness of the worker, watch for cancellation signals.

        Cancellation Detection:
        - Polls the job store at the configured intervals (default: 5 seconds)
        - When cancellation is detected, sets the cancellation event on the execution context
        - stopping the execution is the responsibility of the job executor
        - This means cancellation is not immediate: there can be up to heartbeat_interval_seconds
          delay before detection, plus the time remaining in the current execution step

        Important: Execution stops gracefully at the next checkpoint, ensuring the current
        step completes fully before termination. This prevents partial operations and data corruption.

        :param job_id:
        :param job_execution_ctx:
        :return:
        """
        while self._running:
            await asyncio.sleep(self.heartbeat_interval_seconds)
            if not self._running:
                break
            try:
                heartbeat_job_status = await self.job_store.heartbeat(job_id, self.worker_id)

                if heartbeat_job_status.cancel_requested:
                    logger.warning(
                        "heartbeat detected canceled job. Executing will stop at the next checkpoint",
                        job_id=job_id,
                        worker_id=self.worker_id,
                    )
                    job_execution_ctx.cancel()
                    break
                logger.info("heartbeat", job_id=job_id, worker_id=self.worker_id)
            except JobLeaseLostError:
                logger.error("worker lost the lease for the job, exiting!", job_id=job_id, worker_id=self.worker_id)
                break
            except Exception as exc:
                logger.error("heartbeat failed", job_id=job_id, worker_id=self.worker_id, error=str(exc))
