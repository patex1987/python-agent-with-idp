import pytest
from starlette.testclient import TestClient

from agent_run_worker.in_memory.run_executor import AgentRunExecutor, DummyRunExecutor
from llm_agent.di.fastapi_composition import create_app_with_selected_di
from tests.execution_clients.status_poller import poll_run_status
from tests.fake_implementations.di.ajustable_registrar import ComposableRegistrarProvider
from tests.fake_implementations.di.registrars.dependency_override import DependencyOverrideRegistrar


@pytest.fixture
def agent_service_client_with_instant_execution():
    """
    Synchronous client with development dependencies.

    - The agent run executor is replaced with a dummy one, so
    the execution of the run is instantaneous

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
        factory_overrides={AgentRunExecutor: DummyRunExecutor}, value_overrides={}
    )
    adjusted_registrar_provider = ComposableRegistrarProvider(
        app_lifetime_registrars=[],
        fastapi_lifespan_registrars=[],
        infrastructure_registrars=[agent_executor_override_registrar],
    )
    backend_api_app = create_app_with_selected_di(registrar_provider=adjusted_registrar_provider)
    with TestClient(backend_api_app) as client:
        yield client


class TestAgentRunOrchestration:
    def test_run_executed_successfully(self, agent_service_client_with_instant_execution):
        """
        Integration between the run scheduling rest api and the run status polling.

        creates an agent run and polls until the run is finished. Uses the
        in-memory implementations, and the run execution is replaced with a fake one,
        so the test can validate on the orchestration logic
        """
        response = agent_service_client_with_instant_execution.post(
            "/api/v1/agent/runs",
            json={
                "prompt": "what is the weather like today?",
                "history": [],
            },
        )

        run_id = response.json()["id"]
        assert response.status_code == 200

        response_content = poll_run_status(agent_service_client_with_instant_execution, run_id, timeout_seconds=2)

        assert response_content["status"] == "SUCCEEDED"

