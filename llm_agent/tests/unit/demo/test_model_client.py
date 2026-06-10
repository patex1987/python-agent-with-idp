from __future__ import annotations

import json

import httpx
import pytest

from agent_run_worker.demo.config import DemoAgentSettings
from agent_run_worker.demo.model_client import (
    OpenRouterDemoModelClient,
    build_demo_model_client,
)
from agent_run_worker.demo.trace_context import DemoTraceContext


def test_build_demo_model_client_is_disabled_without_provider_or_key():
    assert build_demo_model_client(DemoAgentSettings(demo_llm_provider="none")) is None
    assert build_demo_model_client(DemoAgentSettings(demo_llm_provider="openrouter", openrouter_api_key=None)) is None


@pytest.mark.asyncio
async def test_openrouter_model_client_posts_configured_chat_completion_request():
    observed: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers["Authorization"]
        observed["referer"] = request.headers["HTTP-Referer"]
        observed["title"] = request.headers["X-OpenRouter-Title"]
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "gen-1",
                "model": "openai/gpt-5.1",
                "choices": [{"message": {"role": "assistant", "content": "recommendation_get_movies"}}],
            },
        )

    client = OpenRouterDemoModelClient(
        DemoAgentSettings(
            demo_llm_provider="openrouter",
            demo_llm_model="openrouter/auto",
            openrouter_api_key="test-key",
            openrouter_base_url="https://openrouter.test/api/v1",
            openrouter_http_referer="https://example.test",
            openrouter_app_title="Demo Agent",
            openrouter_allowed_models="openai/*,anthropic/*",
            openrouter_auto_cost_quality_tradeoff=3,
        ),
        transport=httpx.MockTransport(handler),
    )

    response = await client.complete(
        messages=[
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
        trace_context=_trace_context(),
        workflow_id="workflow-1",
    )

    assert response.content == "recommendation_get_movies"
    assert response.model == "openai/gpt-5.1"
    assert observed["url"] == "https://openrouter.test/api/v1/chat/completions"
    assert observed["authorization"] == "Bearer test-key"
    assert observed["referer"] == "https://example.test"
    assert observed["title"] == "Demo Agent"
    assert observed["payload"] == {
        "model": "openrouter/auto",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
        "temperature": 0.0,
        "max_tokens": 128,
        "session_id": "workflow-1",
        "metadata": {
            "workflow_id": "workflow-1",
            "correlation_id": "corr-1",
            "request_id": "req-1",
        },
        "trace": {
            "trace_id": "11111111111111111111111111111111",
            "trace_name": "demo-agent-reservation",
            "span_name": "agent.reason",
            "generation_name": "next-tool-selection",
        },
        "plugins": [
            {
                "id": "auto-router",
                "allowed_models": ["openai/*", "anthropic/*"],
                "cost_quality_tradeoff": 3,
            }
        ],
    }


def _trace_context() -> DemoTraceContext:
    return DemoTraceContext(
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        correlation_id="corr-1",
        request_id="req-1",
        workflow_id="workflow-1",
    )
