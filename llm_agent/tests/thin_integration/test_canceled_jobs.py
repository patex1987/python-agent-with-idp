import asyncio
from uuid import UUID

import pytest
import structlog
from starlette.testclient import TestClient

from agent_job_worker.in_memory.job_executor import AgentJobExecutor
from llm_agent.di.fastapi_composition import create_app_with_selected_di
from llm_agent.domain.agent.jobs.execution_context import JobExecutionContext
from llm_agent.services.agent.store import JobProcessingStore
from tests.execution_clients.status_poller import poll_job_status
from tests.fake_implementations.di.ajustable_registrar import ComposableRegistrarProvider
from tests.fake_implementations.di.registrars.dependency_override import DependencyOverrideRegistrar

logger = structlog.getLogger(__name__)


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

        await self.allow_start_processing.wait()

        while not self.allow_finish_processing.is_set():
            if job_execution_ctx.is_cancelled():
                logger.info(f"{worker_id}: job cancelled", job_id=job_id)
                return
            await asyncio.sleep(0.1)

        self._finished.set()
        await job_store.heartbeat(job_id, worker_id)


@pytest.fixture
def signal_controlled_executor():
    return SignalControlledJobExecutor()


@pytest.fixture
def agent_service_client_with_blockable_execution(signal_controlled_executor):
    agent_executor_override_registrar = DependencyOverrideRegistrar(
        factory_overrides={},
        value_overrides={
            AgentJobExecutor: signal_controlled_executor,
        },
    )
    adjusted_registrar_provider = ComposableRegistrarProvider(
        app_lifetime_registrars=[],
        fastapi_lifespan_registrars=[],
        infrastructure_registrars=[agent_executor_override_registrar],
    )
    backend_api_app = create_app_with_selected_di(registrar_provider=adjusted_registrar_provider)
    with TestClient(backend_api_app) as client:
        yield client


class TestCanceledJobExecution:
    def test_canceled_before_start(self, signal_controlled_executor, agent_service_client_with_blockable_execution):
        """
        Job execution is canceled before it starts.
        """
        job_creation_response = agent_service_client_with_blockable_execution.post(
            "/api/v1/agent/create-job",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )

        assert job_creation_response.status_code == 200
        job_id = job_creation_response.json()["id"]
        cancel_response = agent_service_client_with_blockable_execution.post(
            f"/api/v1/agent/jobs/{job_id}/cancel",
        )
        assert cancel_response.status_code == 200

        job_status_response = poll_job_status(agent_service_client_with_blockable_execution, job_id, timeout_seconds=2)
        assert job_status_response["status"] == "CANCELLED"

        signal_controlled_executor.allow_start_processing.set()
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
            "/api/v1/agent/create-job",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )

        assert job_creation_response.status_code == 200
        job_id = job_creation_response.json()["id"]

        signal_controlled_executor.allow_start_processing.set()
        cancel_response = agent_service_client_with_blockable_execution.post(
            f"/api/v1/agent/jobs/{job_id}/cancel",
        )

        assert cancel_response.status_code == 200
        # assert cancel_response.json()["message"] == "Job cancellation requested"

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
            "/api/v1/agent/create-job",
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
