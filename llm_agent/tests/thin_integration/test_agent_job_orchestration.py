import time

import pytest
from starlette.testclient import TestClient

from agent_job_worker.in_memory.job_executor import AgentJobExecutor, DummyJobExecutor
from llm_agent.di.fastapi_composition import create_app_with_selected_di
from llm_agent.domain.agent.jobs.status_code import JobStatusCode
from tests.fake_implementations.di.ajustable_registrar import ComposableRegistrarProvider
from tests.fake_implementations.di.registrars.dependency_override import DependencyOverrideRegistrar


@pytest.fixture
def agent_service_client_with_instant_execution():
    """
    Synchronous client with development dependencies.

    - The agent job executor is replaced with a dummy one, so
    the execution of the job is instantaneous

    ----

    Use `httpx.AsyncClient` if you need async test support.
    e.g.:
        ```
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
        ```
    """
    agent_executor_override_registrar = DependencyOverrideRegistrar(
        factory_overrides={AgentJobExecutor: DummyJobExecutor}, value_overrides={}
    )
    adjusted_registrar_provider = ComposableRegistrarProvider(
        app_lifetime_registrars=[],
        fastapi_lifespan_registrars=[],
        infrastructure_registrars=[agent_executor_override_registrar],
    )
    backend_api_app = create_app_with_selected_di(registrar_provider=adjusted_registrar_provider)
    with TestClient(backend_api_app) as client:
        yield client


def poll_job_status(
    client: TestClient,
    job_id: str,
    timeout_seconds: float = 60.0,
    initial_interval: float = 0.1,
    max_interval: float = 2.0,
    backoff_factor: float = 1.5,
) -> dict:
    """
    Poll job status until terminal state or timeout.

    Uses exponential backoff to avoid excessive polling while still
    being responsive to quick completions.

    :param client: TestClient instance
    :param job_id: Job ID to poll
    :param timeout_seconds: Maximum time to wait
    :param initial_interval: Initial polling interval in seconds
    :param max_interval: Maximum polling interval in seconds
    :param backoff_factor: Multiplier for exponential backoff
    :return: raw job response
    :raises: TimeoutError If job doesn't reach terminal state within timeout

    TODO: move this to a common test polling logic
    TODO: (stretch) use a well-known exponential backoff lib
    """
    start_time = time.time()
    interval = initial_interval
    last_status = None

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(
                f"Job {job_id} did not reach terminal state within {timeout_seconds}s. Last status: {last_status}"
            )

        response = client.get(f"/api/v1/agent/get-job-status/{job_id}")
        response.raise_for_status()  # Raises for 4xx/5xx

        status_data = response.json()
        status = status_data["status"]
        last_status = status

        # Check if we've reached a terminal state
        if status in (JobStatusCode.SUCCEEDED.name, JobStatusCode.FAILED.name):
            return status_data

        # Exponential backoff: increase interval up to max
        time.sleep(interval)
        interval = min(interval * backoff_factor, max_interval)


class TestAgentJobOrchestration:
    def test_job_executed_successfully(self, agent_service_client_with_instant_execution):
        """
        Integration between the job scheduling rest api and the job status polling.

        creates an agent job and polls until the job is finished. Uses the
        in-memory implementations, and the job execution is replaced with a fake one,
        so the test can validate on the orchestration logic
        """
        response = agent_service_client_with_instant_execution.post(
            "/api/v1/agent/create-job",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )

        job_id = response.json()["id"]
        assert response.status_code == 200

        response_content = poll_job_status(agent_service_client_with_instant_execution, job_id, timeout_seconds=2)

        assert response_content["status"] == "SUCCEEDED"
