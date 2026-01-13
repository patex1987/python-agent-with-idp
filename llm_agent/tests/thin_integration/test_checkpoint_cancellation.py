"""
Unit/thin integration tests for checkpoint-based run cancellation.

These tests skip the HTTP layer and focus on the consumer and executor,
using test doubles (real in-memory implementations) instead of mocks.

The key behavior being tested: when a run is cancelled during checkpoint execution,
the checkpoint must complete before execution stops.
"""

import asyncio
from uuid import UUID

import pytest
import structlog

from agent_run_worker.in_memory.consumer import InMemoryConsumer
from agent_run_worker.in_memory.run_executor import AgentRunExecutor
from agent_run_worker.domain.runs.execution_context import RunExecutionContext
from llm_agent.domain.agent.runs.request import RunRequest
from contracts.domain.runs.status_code import RunStatusCode
from agent_run_worker.services.runs.processing_store import RunProcessingStore
from llm_agent.services.agent.transition_policy import RunTransitionPolicy
from local_runtime.event_log.in_memory import InMemoryRunEventLog
from local_runtime.run_signal_queue.queue import InMemoryRunSignalQueue
from local_runtime.run_store.intake import InMemoryRunIntakeStore
from local_runtime.run_store.processing import InMemoryRunProcessingStore

logger = structlog.getLogger(__name__)


class SingleCheckpointExecutor(AgentRunExecutor):
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

    async def execute(self, run_id: UUID, worker_id: str, execution_context: RunExecutionContext):
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
        logger.info(f"{worker_id}: execution started", run_id=run_id)

        if execution_context.is_cancelled():
            logger.info(f"{worker_id}: cancellation detected before checkpoint", run_id=run_id)
            self.execution_cancelled = True
            self.execution_stopped.set()
            return

        self.checkpoint_started.set()
        logger.info(f"{worker_id}: checkpoint started", run_id=run_id)

        await asyncio.sleep(self.checkpoint_duration_seconds)

        self.checkpoint_work_done.set()
        logger.info(f"{worker_id}: checkpoint work done", run_id=run_id)

        if execution_context.is_cancelled():
            await execution_context.emit_event(
                event_type="Checkpoint cancelled",
                payload={"message": "cancellation detected during checkpoint execution"},
            )
            logger.info(
                f"{worker_id}: cancellation detected after checkpoint work, but completing checkpoint anyway",
                run_id=run_id,
            )
            self.execution_cancelled = True

        self.checkpoint_completed.set()
        await execution_context.emit_event(
            event_type="Checkpoint completed",
            payload={"message": "checkpoint execution completed"},
        )
        logger.info(f"{worker_id}: checkpoint completed", run_id=run_id)

        if self.execution_cancelled:
            self.execution_stopped.set()
            return

        logger.info(f"{worker_id}: execution completed normally", run_id=run_id)
        self.execution_stopped.set()


@pytest.fixture
def in_memory_runtime():
    """Create shared in-memory runtime for run store and signal queue."""
    from local_runtime.provider import InMemoryRuntime

    return InMemoryRuntime(
        internal_run_storage={},
        internal_event_logs=InMemoryRunEventLog(),
        run_signal_queue=InMemoryRunSignalQueue(),
    )


@pytest.fixture
def run_intake_store(in_memory_runtime):
    """Create run intake store (for creating/enqueuing runs)."""
    return InMemoryRunIntakeStore(
        internal_run_storage=in_memory_runtime.internal_run_storage,
        internal_event_logs=in_memory_runtime.internal_event_logs,
        run_transition_policy=RunTransitionPolicy(),
    )


@pytest.fixture
def run_processing_store(in_memory_runtime):
    """Create run processing store (for worker to claim/process runs)."""
    return InMemoryRunProcessingStore(
        internal_run_storage=in_memory_runtime.internal_run_storage,
        internal_event_logs=in_memory_runtime.internal_event_logs,
        run_transition_policy=RunTransitionPolicy(),
    )


@pytest.fixture
def run_signal_queue(in_memory_runtime):
    """Get the shared run signal queue."""
    return in_memory_runtime.run_signal_queue


@pytest.fixture
def single_checkpoint_executor():
    """Executor with a single checkpoint (0.5 seconds duration)."""
    return SingleCheckpointExecutor(checkpoint_duration_seconds=0.5)


@pytest.fixture
def consumer(in_memory_runtime, run_processing_store, run_signal_queue, single_checkpoint_executor):
    """Create consumer with fast heartbeat for quick cancellation detection."""
    return InMemoryConsumer(
        run_store=run_processing_store,
        run_signal_queue=run_signal_queue,
        event_log=in_memory_runtime.internal_event_logs,
        worker_id="test_worker",
        run_executor=single_checkpoint_executor,
        heartbeat_interval_seconds=0.1,  # Fast heartbeat for tests
    )


class TestCheckpointCompletionDuringCancellation:
    """
    Tests that validate checkpoint completion behavior during cancellation.

    Key assertion: When cancellation happens during checkpoint execution,
    the checkpoint must complete fully before execution stops.

    TODO: we need deterministic tests, so these should rely on run store's
        event logs as a source of truth
    """

    @pytest.mark.asyncio
    async def test_checkpoint_completes_even_when_cancelled_during_execution(
        self,
        in_memory_runtime,
        run_intake_store,
        run_processing_store,
        run_signal_queue,
        consumer,
        single_checkpoint_executor,
    ):
        """
        Test that a checkpoint completes even if cancellation happens during its execution.

        Flow:
        1. Create and enqueue a run
        2. Start consumer in background
        3. Wait for checkpoint to start
        4. Cancel the run (mark as CANCELLED in store) while checkpoint work is running
        5. Wait for heartbeat to detect cancellation
        6. Verify checkpoint work completes
        7. Verify checkpoint fully completes (heartbeat called)
        8. Verify execution stops after checkpoint completion
        9. Verify run status is CANCELLED
        """

        run_request = RunRequest(
            prompt="test checkpoint cancellation",
            history=[],
            user_id="test_user",
        )
        run_status = await run_intake_store.create_run(run_request)
        run_id = run_status.id
        await run_intake_store.mark_enqueued(run_id)
        await run_signal_queue.notify()

        consumer_task = asyncio.create_task(consumer.consume_and_execute_loop())

        try:
            await asyncio.wait_for(single_checkpoint_executor.checkpoint_started.wait(), timeout=2.0)
            cancelled = await run_intake_store.request_cancellation(run_id)
            assert cancelled, "Run should be cancellable"
            await asyncio.wait_for(single_checkpoint_executor.checkpoint_work_done.wait(), timeout=1.0)
            await asyncio.wait_for(single_checkpoint_executor.checkpoint_completed.wait(), timeout=1.0)
            await asyncio.wait_for(single_checkpoint_executor.execution_stopped.wait(), timeout=1.0)
            assert single_checkpoint_executor.execution_cancelled, "Execution should have detected cancellation"

            final_status = await run_processing_store.get_status(run_id)
            assert final_status.status == RunStatusCode.CANCELLED, "Run should be in CANCELLED status"

            print("events in the store")
            event_log = in_memory_runtime.internal_event_logs
            run_events = await event_log.list(run_id)
            for evt in run_events:
                print(evt)

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
