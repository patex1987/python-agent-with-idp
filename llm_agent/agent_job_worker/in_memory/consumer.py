from typing import Protocol

import structlog

from agent_job_worker.in_memory.job_executor import AgentJobExecutor
from agent_job_worker.in_memory.job_lease import JobLeaseScope
from llm_agent.domain.agent.jobs.claim import ClaimedJob
from llm_agent.domain.agent.jobs.execution_context import JobExecutionContext
from llm_agent.domain.agent.jobs.status_code import JobStatusCode
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobProcessingStore

logger = structlog.get_logger(__name__)


class Consumer(Protocol):
    async def consume_and_execute_loop(self):
        """
        The main entrypoint / workhorse on the consumer side.
        :return:
        """
        ...

    async def shutdown_execution(self): ...


class InMemoryConsumer(Consumer):
    def __init__(
        self,
        job_store: JobProcessingStore,
        job_signal_queue: JobSignalQueue,
        worker_id: str,
        job_executor: AgentJobExecutor,
        heartbeat_interval_seconds: int | float = 5,
    ):
        """

        :param job_store:
        :param job_signal_queue:
        :param worker_id:
        :param job_executor:
        :param heartbeat_interval_seconds:

        TODO: add a proper factory to JobLeaseScope and pass a policy object
            to avoid tight coupling between the consumer and lease scope
        """
        logger.info("Initializing in-memory consumer", worker_id=worker_id)
        self.job_store = job_store
        self.job_signal_queue = job_signal_queue
        self._execution_allowed = True
        self.worker_id = worker_id
        self.job_lease_scope_factory = JobLeaseScope
        self.job_executor = job_executor
        self._current_job_execution_ctx: JobExecutionContext | None = None
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    async def consume_and_execute_loop(self):
        """
        Main consumption loop that claims and executes jobs.

        Shutdown Handling:
        - If shutdown is requested while a job is executing, shutdown_execution()
          will cancel the execution context, causing the executor to stop at the
          next checkpoint
        - If shutdown is requested after a job is claimed but before execution
          starts, the job will remain RUNNING until its lease expires
        - In both cases, lease expiration triggers recovery: TIMED_OUT → RETRYING → ENQUEUED
        - See shutdown_execution() for detailed documentation

        TODO: implement the notifier and hook into relevant events
        TODO: add a concurrent health checker, so it's literally just
            checking if the worker is running
        """
        while self._execution_allowed:
            await self.job_signal_queue.wait()
            try:
                claimed_job = await self.job_store.claim_job(self.worker_id)
            except Exception as e:
                logger.error(f"{self.worker_id}: failed to claim job", error=str(e))
                claimed_job = None

            if not claimed_job:
                continue

            if not self._execution_allowed:
                logger.info(f"{self.worker_id}: shutting down")
                break

            job_execution_ctx = JobExecutionContext(job_id=claimed_job.id)
            self._current_job_execution_ctx = job_execution_ctx

            logger.info(f"{self.worker_id}: claimed job", job_id=claimed_job.id)
            async with self.job_lease_scope_factory(
                worker_id=self.worker_id,
                job_id=claimed_job.id,
                job_store=self.job_store,
                job_execution_context=job_execution_ctx,
                heartbeat_interval_seconds=self.heartbeat_interval_seconds,
            ):
                await self.execute_job(claimed_job=claimed_job)

    async def execute_job(self, *, claimed_job: ClaimedJob):
        """
        Execute a claimed job with checkpoint-based cancellation support.

        Cancellation Behavior:
        - The job executor checks for cancellation at checkpoints (between steps)
        - If cancellation is detected, the executor returns gracefully after completing
          the current step
        - After execution completes, we check if cancellation occurred
        - If cancelled, we log but do not mark as succeeded (job is already CANCELLED in store)
        - If not cancelled, we mark the job as succeeded

        Important: Execution stops after finishing the current checkpoint, ensuring
        operations complete atomically and preventing partial state or data corruption.

        :param claimed_job: The job to execute
        """
        job_id = claimed_job.id
        logger.info(f"{self.worker_id}: executing job", job_id=job_id)

        try:
            await self.job_executor.execute(
                job_id=job_id,
                worker_id=self.worker_id,
                job_store=self.job_store,
                job_execution_ctx=self._current_job_execution_ctx,
            )

            if self._current_job_execution_ctx.is_cancelled():
                await self.job_store.set_cancelled(job_id)
                logger.info(f"{self.worker_id}: job cancelled", job_id=job_id)
                return

            job_status = await self.job_store.get_status(job_id)

            if job_status.cancel_requested:
                await self.job_store.set_cancelled(job_id)
                logger.info(
                    f"{self.worker_id}: job cancelled (observed after execution)",
                    job_id=job_id,
                )
                return

            logger.info(f"{self.worker_id}: job done", job_id=job_id)
            await self.job_store.set_succeeded(job_id, {"ok": True})

        except Exception as exc:
            logger.error(
                f"{self.worker_id}: job failed",
                job_id=job_id,
                error=str(exc),
            )
            await self.job_store.set_failed(job_id, str(exc))

        finally:
            self._current_job_execution_ctx = None

    async def shutdown_execution(self):
        """
        Gracefully shutdown the consumer.

        Shutdown Behavior:
        - Stops accepting new jobs by setting _execution_allowed = False
        - If a job is currently executing, cancels its execution context
          (this signals the executor to stop at the next checkpoint)
        - Sends a notification signal to wake up the consumption loop

        Important: Shutdown does NOT mark the job as CANCELLED in the store.
        The job will remain RUNNING until its lease expires. This is intentional:
        - Lease expiration triggers automatic recovery: TIMED_OUT → RETRYING → ENQUEUED
        - This allows the job to be retried by another worker if the current worker
          crashes or shuts down unexpectedly
        - Only store-driven cancellation (via mark_cancelled) marks jobs as CANCELLED

        This design ensures that worker shutdowns don't permanently cancel jobs,
        but rather allow them to be recovered and retried by other workers.
        """
        self._execution_allowed = False

        if self._current_job_execution_ctx:
            self._current_job_execution_ctx.cancel()

        await self.job_signal_queue.notify()
