import asyncio
import uuid

import structlog

from agent_run_worker.domain.exception import RunLeaseLostError
from llm_agent.domain.agent.runs.execution_context import RunExecutionContext
from llm_agent.services.agent.store import RunProcessingStore

logger = structlog.get_logger(__name__)


class RunLeaseScope:
    """
    Maintains run liveness while a worker is executing a claimed run.

    Responsibilities:
    - periodically renew the run lease via heartbeats
    - ensure the run is released if execution stops
    - scope liveness strictly to the execution lifetime

    Note: Do NOT add business timeouts here, that should be handled by
        the agent.
    """

    def __init__(
        self,
        worker_id: str,
        run_id: uuid.UUID,
        run_store: RunProcessingStore,
        run_execution_context: RunExecutionContext,
        heartbeat_interval_seconds: int = 5,
    ):
        self.worker_id = worker_id
        self.run_id = run_id
        self.run_store = run_store
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self._execution_ctx: RunExecutionContext = run_execution_context
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    async def __aenter__(self):
        self._running = True
        self._heartbeat_task = asyncio.create_task(self.heartbeat_loop(self.run_id, self._execution_ctx))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def heartbeat_loop(self, run_id: uuid.UUID, run_execution_ctx: RunExecutionContext):
        """
        Periodically check the liveness of the worker, watch for cancellation signals.

        Cancellation Detection:
        - Polls the run store at the configured intervals (default: 5 seconds)
        - When cancellation is detected, sets the cancellation event on the execution context
        - stopping the execution is the responsibility of the run executor
        - This means cancellation is not immediate: there can be up to heartbeat_interval_seconds
          delay before detection, plus the time remaining in the current execution step

        Important: Execution stops gracefully at the next checkpoint, ensuring the current
        step completes fully before termination. This prevents partial operations and data corruption.

        :param run_id:
        :param run_execution_ctx:
        :return:
        """
        while self._running:
            await asyncio.sleep(self.heartbeat_interval_seconds)
            if not self._running:
                break
            try:
                heartbeat_run_status = await self.run_store.heartbeat(run_id, self.worker_id)

                if heartbeat_run_status.cancel_requested:
                    logger.warning(
                        "heartbeat detected canceled run. Executing will stop at the next checkpoint",
                        run_id=run_id,
                        worker_id=self.worker_id,
                    )
                    run_execution_ctx.cancel()
                    break
                logger.info("heartbeat", run_id=run_id, worker_id=self.worker_id)
            except RunLeaseLostError:
                logger.error("worker lost the lease for the run, exiting!", run_id=run_id, worker_id=self.worker_id)
                break
            except Exception as exc:
                logger.error("heartbeat failed", run_id=run_id, worker_id=self.worker_id, error=str(exc))

