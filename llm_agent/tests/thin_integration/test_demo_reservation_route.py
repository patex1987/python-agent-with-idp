from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from agent_run_worker.demo.trace_context import DemoTraceContext
from agent_run_worker.demo.types import (
    DemoDependencyError,
    DemoReservationRequest,
    DemoReservationResult,
    DemoToolResult,
)
from llm_agent.di.fastapi_composition import create_app_with_selected_di
from llm_agent.services.demo.reservation_service import DemoReservationService
from tests.fake_implementations.di.ajustable_registrar import ComposableRegistrarProvider
from tests.fake_implementations.di.registrars.dependency_override import DependencyOverrideRegistrar


@pytest.fixture
def demo_client():
    with make_demo_client(FakeDemoReservationService()) as client:
        yield client


@pytest.fixture
def failing_demo_client():
    with make_demo_client(FailingDemoReservationService()) as client:
        yield client


def make_demo_client(service: object):
    override_registrar = DependencyOverrideRegistrar(
        factory_overrides={DemoReservationService: lambda: service},
        value_overrides={},
    )
    registrar_provider = ComposableRegistrarProvider(
        app_lifetime_registrars=[],
        fastapi_lifespan_registrars=[override_registrar],
        infrastructure_registrars=[],
    )
    app = create_app_with_selected_di(registrar_provider=registrar_provider)
    return TestClient(app)


def test_demo_health_is_public(demo_client: TestClient):
    response = demo_client.get("/api/v1/demo/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "movie-agent-worker"}


def test_reserve_recommended_seat_returns_workflow_response(demo_client: TestClient):
    response = demo_client.post(
        "/api/v1/demo/reserve-recommended-seat",
        headers={
            "X-Correlation-Id": "corr-route",
            "X-Request-Id": "req-route",
        },
        json={
            "movie_preference": "exciting",
            "seat_preference": "aisle",
            "fault": "none",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["outcome"] == "confirmed"
    assert body["trace"]["correlation_id"] == "corr-route"
    assert body["trace"]["request_id"] == "req-route"
    assert body["tool_results"] == [{"tool_name": "recommendation_get_movies", "outcome": "succeeded"}]


def test_reserve_recommended_seat_validates_fault(demo_client: TestClient):
    response = demo_client.post(
        "/api/v1/demo/reserve-recommended-seat",
        json={
            "movie_preference": "exciting",
            "seat_preference": "aisle",
            "fault": "bad-fault",
        },
    )

    assert response.status_code == 422


def test_reserve_recommended_seat_returns_direct_dependency_error_body(failing_demo_client: TestClient):
    response = failing_demo_client.post(
        "/api/v1/demo/reserve-recommended-seat",
        headers={
            "X-Correlation-Id": "corr-route",
            "X-Request-Id": "req-route",
        },
        json={
            "movie_preference": "exciting",
            "seat_preference": "aisle",
            "fault": "recommendation-error",
        },
    )

    body = response.json()
    assert response.status_code == 502
    assert body["error"] == "demo_dependency_failed"
    assert body["message"] == "dependency failed"
    assert body["trace"]["correlation_id"] == "corr-route"


class FakeDemoReservationService:
    async def reserve_recommended_seat(self, request: DemoReservationRequest) -> DemoReservationResult:
        return DemoReservationResult(
            workflow_id=request.trace_context.workflow_id,
            outcome="confirmed",
            reservation_status="confirmed",
            reservation_request_id="request-1",
            final_answer="Reserved a recommended screening.",
            trace_context=DemoTraceContext(
                traceparent=request.trace_context.traceparent,
                tracestate=request.trace_context.tracestate,
                correlation_id=request.trace_context.correlation_id,
                request_id=request.trace_context.request_id,
                workflow_id=request.trace_context.workflow_id,
            ),
            movie={"id": "movie-1"},
            screening={"id": "screening-1"},
            seat={"id": "seat-1"},
            tool_results=[DemoToolResult("recommendation_get_movies", "succeeded", {})],
        )


class FailingDemoReservationService:
    async def reserve_recommended_seat(self, request: DemoReservationRequest) -> DemoReservationResult:
        result = DemoReservationResult(
            workflow_id=request.trace_context.workflow_id,
            outcome="dependency_failed",
            reservation_status=None,
            reservation_request_id=None,
            final_answer="A dependency failed during the reservation workflow.",
            trace_context=request.trace_context,
            tool_results=[],
            error="dependency failed",
        )
        raise DemoDependencyError(result)
