import asyncio
import random
from typing import Protocol
from uuid import UUID

import structlog

from llm_agent.domain.agent.jobs.execution_context import JobExecutionContext
from llm_agent.services.agent.store import JobProcessingStore

logger = structlog.get_logger(__name__)


class AgentJobExecutor(Protocol):
    async def execute(
        self, job_id: UUID, worker_id: str, job_store: JobProcessingStore, job_execution_ctx: JobExecutionContext
    ):
        """
        Contract for executing agent jobs by the consumer.

        Cancellation Handling:
        - Must check job_execution_ctx.is_cancelled() at checkpoints (between steps/operations)
        - When cancellation is detected, return gracefully after completing the current step
        - Do NOT interrupt operations mid-execution - always finish the current step first
        - This ensures atomic operations and prevents partial state or data corruption

        Checkpoints should be placed:
        - Before starting a new step/operation
        - After completing a step/operation
        - Before any long-running operations

        :param job_id:
        :param worker_id:
        :param job_store:
        :param job_execution_ctx: Context for checking cancellation status at checkpoints
        :return:
        """
        ...


class RandomSleepJobExecutor(AgentJobExecutor):
    async def execute(
        self, job_id: UUID, worker_id: str, job_store: JobProcessingStore, job_execution_ctx: JobExecutionContext
    ):
        """
        Emulate actual job execution with multiple checkpoints each with random durations.

        Cancellation Handling:
        - Checks cancellation at checkpoints (before each step)
        - If cancelled, returns gracefully after the current step completes
        - This ensures jobs are never canceled in the middle of a step, preventing
          partial operations and data corruption

        Important: Execution stops after finishing the current checkpoint, not immediately.
        This means if cancellation is detected, the current step will complete fully
        before the executor returns.

        :param job_id:
        :param worker_id:
        :param job_store:
        :param job_execution_ctx: Context for checking cancellation status at checkpoints
        :return:
        """
        for i in range(5):
            if job_execution_ctx.is_cancelled():
                logger.info(f"{worker_id}: job cancelled", job_id=job_id)
                return
            logger.info(f"{worker_id}: Running job step", job_id=job_id, step=i)
            step_execution_time = random.randint(0, 8)
            await asyncio.sleep(step_execution_time)
            await job_store.heartbeat(job_id, worker_id)
            # await self.job_store.set_progress(job_id, i / 5, {"step": i})
            # await notifier.publish(JobEvent(job_id, "progress", {"step": i}))


class DummyJobExecutor(AgentJobExecutor):
    async def execute(
        self, job_id: UUID, worker_id: str, job_store: JobProcessingStore, job_execution_ctx: JobExecutionContext
    ):
        """
        Simple job executor with a single step that takes a short time to execute.

        Cancellation Handling:
        - Checks cancellation at the start (checkpoint)
        - If cancelled, returns immediately without executing the step
        - If not cancelled, executes the step fully before returning
        - This ensures jobs are never canceled in the middle of execution

        Important: Execution stops after finishing the current checkpoint, not immediately.
        For this executor, the checkpoint is at the start, so cancellation is honored
        before any work begins.

        :param job_id:
        :param worker_id:
        :param job_store:
        :param job_execution_ctx: Context for checking cancellation status at checkpoints
        :return:
        """
        if job_execution_ctx.is_cancelled():
            logger.info(f"{worker_id}: job cancelled", job_id=job_id)
            return
        logger.info(f"{worker_id}: Running job step", job_id=job_id)
        await asyncio.sleep(0.2)
        await job_store.heartbeat(job_id, worker_id)
