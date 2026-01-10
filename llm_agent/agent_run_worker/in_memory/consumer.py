from typing import Protocol

import structlog

from agent_run_worker.in_memory.run_executor import AgentRunExecutor
from agent_run_worker.in_memory.run_lease import RunLeaseScope
from llm_agent.domain.agent.runs.claim import ClaimedRun
from llm_agent.domain.agent.runs.execution_context import RunExecutionContext
from llm_agent.services.agent.queue import RunSignalQueue
from llm_agent.services.agent.store import RunProcessingStore

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
        run_store: RunProcessingStore,
        run_signal_queue: RunSignalQueue,
        worker_id: str,
        run_executor: AgentRunExecutor,
        heartbeat_interval_seconds: int | float = 5,
    ):
        """

        :param run_store:
        :param run_signal_queue:
        :param worker_id:
        :param run_executor:
        :param heartbeat_interval_seconds:

        TODO: add a proper factory to RunLeaseScope and pass a policy object
            to avoid tight coupling between the consumer and lease scope
        """
        logger.info("Initializing in-memory consumer", worker_id=worker_id)
        self.run_store = run_store
        self.run_signal_queue = run_signal_queue
        self._execution_allowed = True
        self.worker_id = worker_id
        self.run_lease_scope_factory = RunLeaseScope
        self.run_executor = run_executor
        self._current_run_execution_ctx: RunExecutionContext | None = None
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    async def consume_and_execute_loop(self):
        """
        Main consumption loop that claims and executes runs.

        Shutdown Handling:
        - If shutdown is requested while a run is executing, shutdown_execution()
          will cancel the execution context, causing the executor to stop at the
          next checkpoint
        - If shutdown is requested after a run is claimed but before execution
          starts, the run will remain RUNNING until its lease expires
        - In both cases, lease expiration triggers recovery: TIMED_OUT → RETRYING → ENQUEUED
        - See shutdown_execution() for detailed documentation

        TODO: implement the notifier and hook into relevant events
        TODO: add a concurrent health checker, so it's literally just
            checking if the worker is running
        """
        while self._execution_allowed:
            await self.run_signal_queue.wait()
            try:
                claimed_run = await self.run_store.claim_run(self.worker_id)
            except Exception as e:
                logger.error(f"{self.worker_id}: failed to claim run", error=str(e))
                claimed_run = None

            if not claimed_run:
                continue

            if not self._execution_allowed:
                logger.info(f"{self.worker_id}: shutting down")
                break

            run_execution_ctx = RunExecutionContext(run_id=claimed_run.id)
            self._current_run_execution_ctx = run_execution_ctx

            logger.info(f"{self.worker_id}: claimed run", run_id=claimed_run.id)
            async with self.run_lease_scope_factory(
                worker_id=self.worker_id,
                run_id=claimed_run.id,
                run_store=self.run_store,
                run_execution_context=run_execution_ctx,
                heartbeat_interval_seconds=self.heartbeat_interval_seconds,
            ):
                await self.execute_run(claimed_run=claimed_run)

    async def execute_run(self, *, claimed_run: ClaimedRun):
        """
        Execute a claimed run with checkpoint-based cancellation support.

        Cancellation Behavior:
        - The run executor checks for cancellation at checkpoints (between steps)
        - If cancellation is detected, the executor returns gracefully after completing
          the current step
        - After execution completes, we check if cancellation occurred
        - If cancelled, we log but do not mark as succeeded (run is already CANCELLED in store)
        - If not cancelled, we mark the run as succeeded

        Important: Execution stops after finishing the current checkpoint, ensuring
        operations complete atomically and preventing partial state or data corruption.

        :param claimed_run: The run to execute
        """
        run_id = claimed_run.id
        logger.info(f"{self.worker_id}: executing run", run_id=run_id)

        try:
            await self.run_executor.execute(
                run_id=run_id,
                worker_id=self.worker_id,
                run_store=self.run_store,
                run_execution_ctx=self._current_run_execution_ctx,
            )

            if self._current_run_execution_ctx.is_cancelled():
                await self.run_store.set_cancelled(run_id)
                logger.info(f"{self.worker_id}: run cancelled", run_id=run_id)
                return

            run_status = await self.run_store.get_status(run_id)

            if run_status.cancel_requested:
                await self.run_store.set_cancelled(run_id)
                logger.info(
                    f"{self.worker_id}: run cancelled (observed after execution)",
                    run_id=run_id,
                )
                return

            logger.info(f"{self.worker_id}: run done", run_id=run_id)
            await self.run_store.set_succeeded(run_id, {"ok": True})

        except Exception as exc:
            logger.error(
                f"{self.worker_id}: run failed",
                run_id=run_id,
                error=str(exc),
            )
            await self.run_store.set_failed(run_id, str(exc))

        finally:
            self._current_run_execution_ctx = None

    async def shutdown_execution(self):
        """
        Gracefully shutdown the consumer.

        Shutdown Behavior:
        - Stops accepting new runs by setting _execution_allowed = False
        - If a run is currently executing, cancels its execution context
          (this signals the executor to stop at the next checkpoint)
        - Sends a notification signal to wake up the consumption loop

        Important: Shutdown does NOT mark the run as CANCELLED in the store.
        The run will remain RUNNING until its lease expires. This is intentional:
        - Lease expiration triggers automatic recovery: TIMED_OUT → RETRYING → ENQUEUED
        - This allows the run to be retried by another worker if the current worker
          crashes or shuts down unexpectedly
        - Only store-driven cancellation (via mark_cancelled) marks runs as CANCELLED

        This design ensures that worker shutdowns don't permanently cancel runs,
        but rather allow them to be recovered and retried by other workers.
        """
        self._execution_allowed = False

        if self._current_run_execution_ctx:
            self._current_run_execution_ctx.cancel()

        await self.run_signal_queue.notify()

