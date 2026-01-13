import asyncio
import random
from typing import Protocol
from uuid import UUID

import structlog

from agent_run_worker.domain.runs.execution_context import RunExecutionContext

logger = structlog.get_logger(__name__)


class AgentRunExecutor(Protocol):
    async def execute(self, run_id: UUID, worker_id: str, execution_context: RunExecutionContext):
        """
        Contract for executing agent runs by the consumer.

        Cancellation Handling:
        - Must check execution_context.is_cancelled() at checkpoints (between steps/operations)
        - When cancellation is detected, return gracefully after completing the current step
        - Do NOT interrupt operations mid-execution - always finish the current step first
        - This ensures atomic operations and prevents partial state or data corruption

        Checkpoints should be placed:
        - Before starting a new step/operation
        - After completing a step/operation
        - Before any long-running operations

        Event Emission:
        - Use execution_context.emit_event() to emit events during execution
        - The run_id is automatically included in emitted events

        :param run_id: The ID of the run being executed
        :param worker_id: The ID of the worker executing the run
        :param execution_context: Execution context providing cancellation checking and event emission
        :return:
        """
        ...


class RandomSleepRunExecutor(AgentRunExecutor):
    async def execute(self, run_id: UUID, worker_id: str, execution_context: RunExecutionContext):
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

        :param run_id: The ID of the run being executed
        :param worker_id: The ID of the worker executing the run
        :param execution_context: Execution context providing cancellation checking and event emission
        :return:
        """
        for i in range(5):
            if execution_context.is_cancelled():
                logger.info(f"{worker_id}: run cancelled", run_id=run_id)
                return
            logger.info(f"{worker_id}: Running run step", run_id=run_id, step=i)
            step_execution_time = random.randint(0, 8)
            await asyncio.sleep(step_execution_time)
            # await execution_context.emit_event(event_type="progress", payload={"step": str(i), "total": "5"})


class DummyRunExecutor(AgentRunExecutor):
    async def execute(self, run_id: UUID, worker_id: str, execution_context: RunExecutionContext):
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

        :param run_id: The ID of the run being executed
        :param worker_id: The ID of the worker executing the run
        :param execution_context: Execution context providing cancellation checking and event emission
        :return:
        """
        if execution_context.is_cancelled():
            logger.info(f"{worker_id}: run cancelled", run_id=run_id)
            return
        logger.info(f"{worker_id}: Running run step", run_id=run_id)
        await asyncio.sleep(0.2)
