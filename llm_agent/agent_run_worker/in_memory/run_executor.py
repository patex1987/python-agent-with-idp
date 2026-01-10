import asyncio
import random
from typing import Protocol
from uuid import UUID

import structlog

from llm_agent.domain.agent.runs.execution_context import RunExecutionContext
from llm_agent.services.agent.store import RunProcessingStore

logger = structlog.get_logger(__name__)


class AgentRunExecutor(Protocol):
    async def execute(
        self, run_id: UUID, worker_id: str, run_store: RunProcessingStore, run_execution_ctx: RunExecutionContext
    ):
        """
        Contract for executing agent runs by the consumer.

        Cancellation Handling:
        - Must check run_execution_ctx.is_cancelled() at checkpoints (between steps/operations)
        - When cancellation is detected, return gracefully after completing the current step
        - Do NOT interrupt operations mid-execution - always finish the current step first
        - This ensures atomic operations and prevents partial state or data corruption

        Checkpoints should be placed:
        - Before starting a new step/operation
        - After completing a step/operation
        - Before any long-running operations

        :param run_id:
        :param worker_id:
        :param run_store: Todo: expose the event log instead of the run store only
        :param run_execution_ctx: Context for checking cancellation status at checkpoints
        :return:
        """
        ...


class RandomSleepRunExecutor(AgentRunExecutor):
    async def execute(
        self, run_id: UUID, worker_id: str, run_store: RunProcessingStore, run_execution_ctx: RunExecutionContext
    ):
        """
        Emulate actual run execution with multiple checkpoints each with random durations.

        Cancellation Handling:
        - Checks cancellation at checkpoints (before each step)
        - If cancelled, returns gracefully after the current step completes
        - This ensures runs are never canceled in the middle of a step, preventing
          partial operations and data corruption

        Important: Execution stops after finishing the current checkpoint, not immediately.
        This means if cancellation is detected, the current step will complete fully
        before the executor returns.

        :param run_id:
        :param worker_id:
        :param run_store:
        :param run_execution_ctx: Context for checking cancellation status at checkpoints
        :return:
        """
        for i in range(5):
            if run_execution_ctx.is_cancelled():
                logger.info(f"{worker_id}: run cancelled", run_id=run_id)
                return
            logger.info(f"{worker_id}: Running run step", run_id=run_id, step=i)
            step_execution_time = random.randint(0, 8)
            await asyncio.sleep(step_execution_time)
            # await self.run_store.set_progress(run_id, i / 5, {"step": i})
            # await notifier.publish(RunEvent(run_id, "progress", {"step": i}))


class DummyRunExecutor(AgentRunExecutor):
    async def execute(
        self, run_id: UUID, worker_id: str, run_store: RunProcessingStore, run_execution_ctx: RunExecutionContext
    ):
        """
        Simple run executor with a single step that takes a short time to execute.

        Cancellation Handling:
        - Checks cancellation at the start (checkpoint)
        - If cancelled, returns immediately without executing the step
        - If not cancelled, executes the step fully before returning
        - This ensures runs are never canceled in the middle of execution

        Important: Execution stops after finishing the current checkpoint, not immediately.
        For this executor, the checkpoint is at the start, so cancellation is honored
        before any work begins.

        :param run_id:
        :param worker_id:
        :param run_store:
        :param run_execution_ctx: Context for checking cancellation status at checkpoints
        :return:
        """
        if run_execution_ctx.is_cancelled():
            logger.info(f"{worker_id}: run cancelled", run_id=run_id)
            return
        logger.info(f"{worker_id}: Running run step", run_id=run_id)
        await asyncio.sleep(0.2)

