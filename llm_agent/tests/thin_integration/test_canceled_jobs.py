import asyncio
import time
import uuid
from uuid import UUID

import pytest
import structlog
import svcs
from starlette.testclient import TestClient

from agent_job_worker.in_memory.consumer import Consumer, InMemoryConsumer
from agent_job_worker.in_memory.job_executor import AgentJobExecutor
from llm_agent.di.fastapi_composition import create_app_with_selected_di
from llm_agent.domain.agent.jobs.execution_context import JobExecutionContext
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobProcessingStore
from local_runtime.provider import create_default_in_memory_runtime, InMemoryRuntime
from tests.execution_clients.status_poller import poll_job_status, sync_wait_until
from tests.fake_implementations.agent_job_worker.di.registrars.consumer import ConsumerRegistrar
from tests.fake_implementations.di.ajustable_registrar import ComposableRegistrarProvider
from tests.fake_implementations.llm_agent.di.registrars.job_orchestrator import InMemoryJobOrchestrationRegistrar

logger = structlog.getLogger(__name__)


HEARTBEAT_INTERVAL_SECONDS = 0.1


class SignalControlledJobExecutor(AgentJobExecutor):
    """
    An executor that is blocked until the controller signals are set.
    """

    def __init__(self):
        self.allow_start_processing = asyncio.Event()
        self.allow_finish_processing = asyncio.Event()
        self._started = asyncio.Event()
        self._finished = asyncio.Event()

    async def execute(
        self, job_id: UUID, worker_id: str, job_store: JobProcessingStore, job_execution_ctx: JobExecutionContext
    ):
        self._started.set()

        start_task = asyncio.create_task(self.allow_start_processing.wait())
        cancel_task = asyncio.create_task(job_execution_ctx.cancellation_event.wait())

        done, pending = await asyncio.wait(
            {start_task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        if job_execution_ctx.is_cancelled():
            logger.warning(f"{worker_id}: job cancelled", job_id=job_id, location="executor")
            return

        while not self.allow_finish_processing.is_set():
            if job_execution_ctx.is_cancelled():
                logger.warning(f"{worker_id}: job cancelled", job_id=job_id, location="executor-mid-execution")
                return
            await asyncio.sleep(0.1)

        self._finished.set()


@pytest.fixture
def signal_controlled_executor():
    return SignalControlledJobExecutor()


class FastConsumerRegistrar(ConsumerRegistrar):
    def __init__(self, shared_local_infrastructure: InMemoryRuntime, executor):
        self._shared_local_infrastructure = shared_local_infrastructure
        self._executor = executor

    @classmethod
    def get_consumer(cls, svcs_container: svcs.Container) -> Consumer:
        worker_id = f"worker_{uuid.uuid4()}"
        return InMemoryConsumer(
            job_store=svcs_container.get(JobProcessingStore),
            job_signal_queue=svcs_container.get(JobSignalQueue),
            worker_id=worker_id,
            job_executor=svcs_container.get(AgentJobExecutor),
            heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
        )

    def get_job_executor(self) -> AgentJobExecutor:
        return self._executor


@pytest.fixture
def agent_service_client_with_blockable_execution(signal_controlled_executor):
    memory_runtime = create_default_in_memory_runtime()
    registrar_provider = ComposableRegistrarProvider(
        app_lifetime_registrars=[],
        fastapi_lifespan_registrars=[InMemoryJobOrchestrationRegistrar(memory_runtime)],
        infrastructure_registrars=[FastConsumerRegistrar(memory_runtime, signal_controlled_executor)],
    )

    app = create_app_with_selected_di(registrar_provider=registrar_provider)
    with TestClient(app) as client:
        yield client


class TestCanceledJobExecution:
    def test_canceled_before_start(self, signal_controlled_executor, agent_service_client_with_blockable_execution):
        """
        Test cancellation of a job before execution begins.

        This test simulates cancellation after the job has been claimed by a worker but before
        the executor starts processing. In a real-world scenario, jobs might be cancelled while
        sitting in the queue before being claimed, but this test focuses on the deterministic
        case where cancellation occurs after claiming but before work begins.

        The test uses asyncio events (via SignalControlledJobExecutor) to control execution
        timing deterministically. The executor's _started flag indicates that the job has been
        claimed and execute() has been entered, simulating the "queued but not yet processing"
        state.
        """
        job_creation_response = agent_service_client_with_blockable_execution.post(
            "/api/v1/agent/jobs",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )

        sync_wait_until(lambda: signal_controlled_executor._started.is_set(), what="executor started the execution")

        assert job_creation_response.status_code == 200
        job_id = job_creation_response.json()["id"]
        cancel_response = agent_service_client_with_blockable_execution.post(
            f"/api/v1/agent/jobs/{job_id}/cancel",
        )
        assert cancel_response.status_code == 200

        time.sleep(HEARTBEAT_INTERVAL_SECONDS * 1.5)  # ensure heartbeat runs
        signal_controlled_executor.allow_start_processing.set()
        job_status_response = poll_job_status(agent_service_client_with_blockable_execution, job_id, timeout_seconds=2)
        assert job_status_response["status"] == "CANCELLED"

        signal_controlled_executor.allow_finish_processing.set()

        assert signal_controlled_executor._started.is_set()
        assert not signal_controlled_executor._finished.is_set()

    def test_canceled_during_execution(self, signal_controlled_executor, agent_service_client_with_blockable_execution):
        """
        Job execution is canceled during execution.

        - we allow to start the processing
        - send a cancel signal
        - allow to finish the processing, but the job should already be marked as cancelled
        - the _finished event should never be set
        """
        job_creation_response = agent_service_client_with_blockable_execution.post(
            "/api/v1/agent/jobs",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )
        sync_wait_until(lambda: signal_controlled_executor._started.is_set(), what="executor started the execution")

        assert job_creation_response.status_code == 200
        job_id = job_creation_response.json()["id"]

        signal_controlled_executor.allow_start_processing.set()

        cancel_response = agent_service_client_with_blockable_execution.post(
            f"/api/v1/agent/jobs/{job_id}/cancel",
        )

        assert cancel_response.status_code == 200
        # assert cancel_response.json()["message"] == "Job cancellation requested"

        time.sleep(HEARTBEAT_INTERVAL_SECONDS * 1.5)  # ensure heartbeat runs
        signal_controlled_executor.allow_finish_processing.set()

        job_status_response = poll_job_status(agent_service_client_with_blockable_execution, job_id, timeout_seconds=2)
        assert job_status_response["status"] == "CANCELLED"

        assert signal_controlled_executor._started.is_set()
        assert not signal_controlled_executor._finished.is_set()

    def test_canceled_after_execution(self, signal_controlled_executor, agent_service_client_with_blockable_execution):
        """
        Job execution is canceled after execution.

        Job is executed successfully, cancellation signal is sent afterward,
        as such cancellation has no effect.
        """
        job_creation_response = agent_service_client_with_blockable_execution.post(
            "/api/v1/agent/jobs",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )

        assert job_creation_response.status_code == 200
        job_id = job_creation_response.json()["id"]

        signal_controlled_executor.allow_start_processing.set()
        signal_controlled_executor.allow_finish_processing.set()

        signal_controlled_executor.allow_start_processing.set()
        cancel_response = agent_service_client_with_blockable_execution.post(
            f"/api/v1/agent/jobs/{job_id}/cancel",
        )

        assert cancel_response.status_code == 200
        # assert cancel_response.json()["message"] == "Job already in terminal state"

        job_status_response = poll_job_status(agent_service_client_with_blockable_execution, job_id, timeout_seconds=2)
        assert job_status_response["status"] == "SUCCEEDED"
        assert signal_controlled_executor._started.is_set()
        assert signal_controlled_executor._finished.is_set()
