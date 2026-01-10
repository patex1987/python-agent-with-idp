import asyncio
import time
import uuid
from uuid import UUID

import pytest
import structlog
import svcs
from starlette.testclient import TestClient

from agent_run_worker.in_memory.consumer import Consumer, InMemoryConsumer
from agent_run_worker.in_memory.run_executor import AgentRunExecutor
from llm_agent.di.fastapi_composition import create_app_with_selected_di
from llm_agent.domain.agent.runs.execution_context import RunExecutionContext
from llm_agent.services.agent.queue import RunSignalQueue
from llm_agent.services.agent.store import RunProcessingStore
from local_runtime.provider import create_default_in_memory_runtime, InMemoryRuntime
from tests.execution_clients.status_poller import poll_run_status, sync_wait_until
from tests.fake_implementations.agent_run_worker.di.registrars.consumer import ConsumerRegistrar
from tests.fake_implementations.di.ajustable_registrar import ComposableRegistrarProvider
from tests.fake_implementations.llm_agent.di.registrars.run_orchestrator import InMemoryRunOrchestrationRegistrar

logger = structlog.getLogger(__name__)


HEARTBEAT_INTERVAL_SECONDS = 0.1


class SignalControlledRunExecutor(AgentRunExecutor):
    """
    An executor that is blocked until the controller signals are set.
    """

    def __init__(self):
        self.allow_start_processing = asyncio.Event()
        self.allow_finish_processing = asyncio.Event()
        self._started = asyncio.Event()
        self._finished = asyncio.Event()

    async def execute(
        self, run_id: UUID, worker_id: str, run_store: RunProcessingStore, run_execution_ctx: RunExecutionContext
    ):
        self._started.set()

        start_task = asyncio.create_task(self.allow_start_processing.wait())
        cancel_task = asyncio.create_task(run_execution_ctx.cancellation_event.wait())

        done, pending = await asyncio.wait(
            {start_task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        if run_execution_ctx.is_cancelled():
            logger.warning(f"{worker_id}: run cancelled", run_id=run_id, location="executor")
            return

        while not self.allow_finish_processing.is_set():
            if run_execution_ctx.is_cancelled():
                logger.warning(f"{worker_id}: run cancelled", run_id=run_id, location="executor-mid-execution")
                return
            await asyncio.sleep(0.1)

        self._finished.set()


@pytest.fixture
def signal_controlled_executor():
    return SignalControlledRunExecutor()


class FastConsumerRegistrar(ConsumerRegistrar):
    def __init__(self, shared_local_infrastructure: InMemoryRuntime, executor):
        self._shared_local_infrastructure = shared_local_infrastructure
        self._executor = executor

    @classmethod
    def get_consumer(cls, svcs_container: svcs.Container) -> Consumer:
        worker_id = f"worker_{uuid.uuid4()}"
        return InMemoryConsumer(
            run_store=svcs_container.get(RunProcessingStore),
            run_signal_queue=svcs_container.get(RunSignalQueue),
            worker_id=worker_id,
            run_executor=svcs_container.get(AgentRunExecutor),
            heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
        )

    def get_run_executor(self) -> AgentRunExecutor:
        return self._executor


@pytest.fixture
def agent_service_client_with_blockable_execution(signal_controlled_executor):
    memory_runtime = create_default_in_memory_runtime()
    registrar_provider = ComposableRegistrarProvider(
        app_lifetime_registrars=[],
        fastapi_lifespan_registrars=[InMemoryRunOrchestrationRegistrar(memory_runtime)],
        infrastructure_registrars=[FastConsumerRegistrar(memory_runtime, signal_controlled_executor)],
    )

    app = create_app_with_selected_di(registrar_provider=registrar_provider)
    with TestClient(app) as client:
        yield client


class TestCanceledRunExecution:
    def test_canceled_before_start(self, signal_controlled_executor, agent_service_client_with_blockable_execution):
        """
        Test cancellation of a run before execution begins.

        This test simulates cancellation after the run has been claimed by a worker but before
        the executor starts processing. In a real-world scenario, runs might be cancelled while
        sitting in the queue before being claimed, but this test focuses on the deterministic
        case where cancellation occurs after claiming but before work begins.

        The test uses asyncio events (via SignalControlledRunExecutor) to control execution
        timing deterministically. The executor's _started flag indicates that the run has been
        claimed and execute() has been entered, simulating the "queued but not yet processing"
        state.
        """
        run_creation_response = agent_service_client_with_blockable_execution.post(
            "/api/v1/agent/runs",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )

        sync_wait_until(lambda: signal_controlled_executor._started.is_set(), what="executor started the execution")

        assert run_creation_response.status_code == 200
        run_id = run_creation_response.json()["id"]
        cancel_response = agent_service_client_with_blockable_execution.post(
            f"/api/v1/agent/runs/{run_id}/cancel",
        )
        assert cancel_response.status_code == 200

        time.sleep(HEARTBEAT_INTERVAL_SECONDS * 1.5)  # ensure heartbeat runs
        signal_controlled_executor.allow_start_processing.set()
        run_status_response = poll_run_status(agent_service_client_with_blockable_execution, run_id, timeout_seconds=2)
        assert run_status_response["status"] == "CANCELLED"

        signal_controlled_executor.allow_finish_processing.set()

        assert signal_controlled_executor._started.is_set()
        assert not signal_controlled_executor._finished.is_set()

    def test_canceled_during_execution(self, signal_controlled_executor, agent_service_client_with_blockable_execution):
        """
        Run execution is canceled during execution.

        - we allow to start the processing
        - send a cancel signal
        - allow to finish the processing, but the run should already be marked as cancelled
        - the _finished event should never be set
        """
        run_creation_response = agent_service_client_with_blockable_execution.post(
            "/api/v1/agent/runs",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )
        sync_wait_until(lambda: signal_controlled_executor._started.is_set(), what="executor started the execution")

        assert run_creation_response.status_code == 200
        run_id = run_creation_response.json()["id"]

        signal_controlled_executor.allow_start_processing.set()

        cancel_response = agent_service_client_with_blockable_execution.post(
            f"/api/v1/agent/runs/{run_id}/cancel",
        )

        assert cancel_response.status_code == 200
        # assert cancel_response.json()["message"] == "Run cancellation requested"

        time.sleep(HEARTBEAT_INTERVAL_SECONDS * 1.5)  # ensure heartbeat runs
        signal_controlled_executor.allow_finish_processing.set()

        run_status_response = poll_run_status(agent_service_client_with_blockable_execution, run_id, timeout_seconds=2)
        assert run_status_response["status"] == "CANCELLED"

        assert signal_controlled_executor._started.is_set()
        assert not signal_controlled_executor._finished.is_set()

    def test_canceled_after_execution(self, signal_controlled_executor, agent_service_client_with_blockable_execution):
        """
        Run execution is canceled after execution.

        Run is executed successfully, cancellation signal is sent afterward,
        as such cancellation has no effect.
        """
        run_creation_response = agent_service_client_with_blockable_execution.post(
            "/api/v1/agent/runs",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )

        assert run_creation_response.status_code == 200
        run_id = run_creation_response.json()["id"]

        signal_controlled_executor.allow_start_processing.set()
        signal_controlled_executor.allow_finish_processing.set()

        signal_controlled_executor.allow_start_processing.set()
        cancel_response = agent_service_client_with_blockable_execution.post(
            f"/api/v1/agent/runs/{run_id}/cancel",
        )

        assert cancel_response.status_code == 200
        # assert cancel_response.json()["message"] == "Run already in terminal state"

        run_status_response = poll_run_status(agent_service_client_with_blockable_execution, run_id, timeout_seconds=2)
        assert run_status_response["status"] == "SUCCEEDED"
        assert signal_controlled_executor._started.is_set()
        assert signal_controlled_executor._finished.is_set()

