"""
Unit/thin integration tests for checkpoint-based job cancellation.

These tests skip the HTTP layer and focus on the consumer and executor,
using test doubles (real in-memory implementations) instead of mocks.

The key behavior being tested: when a job is cancelled during checkpoint execution,
the checkpoint must complete before execution stops.
"""

import asyncio
from uuid import UUID

import pytest
import structlog

from agent_job_worker.in_memory.consumer import InMemoryConsumer
from agent_job_worker.in_memory.job_executor import AgentJobExecutor
from llm_agent.domain.agent.jobs.execution_context import JobExecutionContext
from llm_agent.domain.agent.jobs.request import JobRequest
from llm_agent.domain.agent.jobs.status_code import JobStatusCode
from llm_agent.services.agent.store import JobProcessingStore
from llm_agent.services.agent.transition_policy import JobTransitionPolicy
from local_runtime.job_signal_queue.queue import InMemoryJobSignalQueue
from local_runtime.job_store.intake import InMemoryJobIntakeStore
from local_runtime.job_store.processing import InMemoryJobProcessingStore

logger = structlog.getLogger(__name__)


class SingleCheckpointExecutor(AgentJobExecutor):
    """
    Test double executor with a single checkpoint.

    Provides observable state to validate checkpoint behavior:
    - checkpoint_started: set when checkpoint begins
    - checkpoint_work_done: set when checkpoint work completes
    - checkpoint_completed: set when checkpoint fully completes
    - execution_stopped: set when execution stops (due to cancellation or completion)
    """

    def __init__(self, checkpoint_duration_seconds: float = 0.2):
        """
        :param checkpoint_duration_seconds: Fixed duration for checkpoint work (deterministic)
        """
        self.checkpoint_duration_seconds = checkpoint_duration_seconds

        # Observable state - asyncio.Event for async test access
        self.checkpoint_started = asyncio.Event()
        self.checkpoint_work_done = asyncio.Event()
        self.checkpoint_completed = asyncio.Event()
        self.execution_stopped = asyncio.Event()

        # Track execution state
        self.execution_cancelled = False

    async def execute(
        self,
        job_id: UUID,
        worker_id: str,
        job_store: JobProcessingStore,
        job_execution_ctx: JobExecutionContext,
    ):
        """
        Execute a single checkpoint with cancellation checks.

        The checkpoint has two phases:
        1. Work phase: does the actual work (sleeps for checkpoint_duration_seconds)
        2. Completion phase: calls heartbeat, marks checkpoint as complete

        Cancellation is checked:
        - Before starting the checkpoint
        - After completing checkpoint work (before heartbeat)

        This ensures that if cancellation happens during the work phase,
        the checkpoint still completes fully before execution stops.
        """
        logger.info(f"{worker_id}: execution started", job_id=job_id)

        if job_execution_ctx.is_cancelled():
            logger.info(f"{worker_id}: cancellation detected before checkpoint", job_id=job_id)
            self.execution_cancelled = True
            self.execution_stopped.set()
            return

        self.checkpoint_started.set()
        logger.info(f"{worker_id}: checkpoint started", job_id=job_id)

        await asyncio.sleep(self.checkpoint_duration_seconds)

        self.checkpoint_work_done.set()
        logger.info(f"{worker_id}: checkpoint work done", job_id=job_id)

        if job_execution_ctx.is_cancelled():
            logger.info(
                f"{worker_id}: cancellation detected after checkpoint work, but completing checkpoint anyway",
                job_id=job_id,
            )
            self.execution_cancelled = True

        await job_store.heartbeat(job_id, worker_id)

        self.checkpoint_completed.set()
        logger.info(f"{worker_id}: checkpoint completed", job_id=job_id)

        if self.execution_cancelled:
            self.execution_stopped.set()
            return

        logger.info(f"{worker_id}: execution completed normally", job_id=job_id)
        self.execution_stopped.set()


@pytest.fixture
def in_memory_runtime():
    """Create shared in-memory runtime for job store and signal queue."""
    from collections import deque
    from local_runtime.provider import InMemoryRuntime

    return InMemoryRuntime(
        internal_job_storage={},
        internal_event_logs={},
        job_signal_queue=InMemoryJobSignalQueue(),
    )


@pytest.fixture
def job_intake_store(in_memory_runtime):
    """Create job intake store (for creating/enqueuing jobs)."""
    return InMemoryJobIntakeStore(
        internal_job_storage=in_memory_runtime.internal_job_storage,
        internal_event_logs=in_memory_runtime.internal_event_logs,
        job_transition_policy=JobTransitionPolicy(),
    )


@pytest.fixture
def job_processing_store(in_memory_runtime):
    """Create job processing store (for worker to claim/process jobs)."""
    return InMemoryJobProcessingStore(
        internal_job_storage=in_memory_runtime.internal_job_storage,
        internal_event_logs=in_memory_runtime.internal_event_logs,
        job_transition_policy=JobTransitionPolicy(),
    )


@pytest.fixture
def job_signal_queue(in_memory_runtime):
    """Get the shared job signal queue."""
    return in_memory_runtime.job_signal_queue


@pytest.fixture
def single_checkpoint_executor():
    """Executor with a single checkpoint (0.5 seconds duration)."""
    return SingleCheckpointExecutor(checkpoint_duration_seconds=0.5)


@pytest.fixture
def consumer(job_processing_store, job_signal_queue, single_checkpoint_executor):
    """Create consumer with fast heartbeat for quick cancellation detection."""
    return InMemoryConsumer(
        job_store=job_processing_store,
        job_signal_queue=job_signal_queue,
        worker_id="test_worker",
        job_executor=single_checkpoint_executor,
        heartbeat_interval_seconds=0.1,  # Fast heartbeat for tests
    )


class TestCheckpointCompletionDuringCancellation:
    """
    Tests that validate checkpoint completion behavior during cancellation.

    Key assertion: When cancellation happens during checkpoint execution,
    the checkpoint must complete fully before execution stops.

    TODO: we need deterministic tests, so these should rely on job store's
        event logs as a source of truth
    """

    @pytest.mark.asyncio
    async def test_checkpoint_completes_even_when_cancelled_during_execution(
        self,
        job_intake_store,
        job_processing_store,
        job_signal_queue,
        consumer,
        single_checkpoint_executor,
    ):
        """
        Test that a checkpoint completes even if cancellation happens during its execution.

        Flow:
        1. Create and enqueue a job
        2. Start consumer in background
        3. Wait for checkpoint to start
        4. Cancel the job (mark as CANCELLED in store) while checkpoint work is running
        5. Wait for heartbeat to detect cancellation
        6. Verify checkpoint work completes
        7. Verify checkpoint fully completes (heartbeat called)
        8. Verify execution stops after checkpoint completion
        9. Verify job status is CANCELLED
        """

        job_request = JobRequest(
            prompt="test checkpoint cancellation",
            history=[],
            user_id="test_user",
        )
        job_status = await job_intake_store.create_job(job_request)
        job_id = job_status.id
        await job_intake_store.mark_enqueued(job_id)
        await job_signal_queue.notify()

        consumer_task = asyncio.create_task(consumer.consume_and_execute_loop())

        try:
            await asyncio.wait_for(single_checkpoint_executor.checkpoint_started.wait(), timeout=2.0)

            cancelled = await job_intake_store.mark_cancelled(job_id)
            assert cancelled, "Job should be cancellable"

            await asyncio.sleep(1.0)

            assert single_checkpoint_executor.checkpoint_work_done.is_set(), (
                "Checkpoint work should complete even after cancellation"
            )

            await asyncio.wait_for(single_checkpoint_executor.checkpoint_completed.wait(), timeout=1.0)

            await asyncio.wait_for(single_checkpoint_executor.execution_stopped.wait(), timeout=1.0)

            assert single_checkpoint_executor.execution_cancelled, "Execution should have detected cancellation"

            final_status = await job_processing_store.get_status(job_id)
            assert final_status.status == JobStatusCode.CANCELLED, "Job should be in CANCELLED status"

        finally:
            await consumer.shutdown_execution()
            try:
                await asyncio.wait_for(consumer_task, timeout=2.0)
            except asyncio.TimeoutError:
                consumer_task.cancel()
                try:
                    await consumer_task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_job_not_claimed_when_cancelled_before_consumer_starts(
        self,
        job_intake_store,
        job_processing_store,
        job_signal_queue,
        consumer,
        single_checkpoint_executor,
    ):
        """
        Test that a job cancelled before consumer starts is never claimed or executed.

        Flow:
        1. Create and enqueue a job
        2. Cancel the job before consumer starts
        3. Start consumer
        4. Verify job is never claimed (remains CANCELLED, not RUNNING)
        5. Verify executor never runs (checkpoint never starts)

        Note: This is different from cancellation during execution. When cancelled
        before consumer starts, the job is in CANCELLED state, so claim_job()
        won't claim it (only ENQUEUED jobs are claimable).
        """

        job_request = JobRequest(
            prompt="test cancellation before consumer starts",
            history=[],
            user_id="test_user",
        )
        job_status = await job_intake_store.create_job(job_request)
        job_id = job_status.id
        await job_intake_store.mark_enqueued(job_id)

        cancelled = await job_intake_store.mark_cancelled(job_id)
        assert cancelled, "Job should be cancellable"

        status = await job_processing_store.get_status(job_id)
        assert status.status == JobStatusCode.CANCELLED, "Job should be CANCELLED after cancellation"

        await job_signal_queue.notify()
        consumer_task = asyncio.create_task(consumer.consume_and_execute_loop())

        try:
            await asyncio.sleep(0.3)

            assert not single_checkpoint_executor.checkpoint_started.is_set(), (
                "Checkpoint should not start - job should not be claimed"
            )

            assert not single_checkpoint_executor.execution_stopped.is_set(), (
                "Execution should not run - job was never claimed"
            )

            final_status = await job_processing_store.get_status(job_id)
            assert final_status.status == JobStatusCode.CANCELLED, (
                "Job should remain CANCELLED and never transition to RUNNING"
            )

        finally:
            await consumer.shutdown_execution()
            try:
                await asyncio.wait_for(consumer_task, timeout=2.0)
            except asyncio.TimeoutError:
                consumer_task.cancel()
                try:
                    await consumer_task
                except asyncio.CancelledError:
                    pass
