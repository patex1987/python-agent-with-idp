from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from opentelemetry.trace import Status, StatusCode

from agent_run_worker.demo.config import DemoAgentSettings
from agent_run_worker.demo.trace_context import DemoTraceContext
from llm_agent.core.telemetry import get_tracer, set_span_attributes


@dataclass(frozen=True)
class DemoModelResponse:
    content: str
    model: str | None
    generation_id: str | None = None


class DemoModelClient(Protocol):
    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        trace_context: DemoTraceContext,
        workflow_id: str,
    ) -> DemoModelResponse: ...


class DemoModelClientError(RuntimeError):
    pass


class OpenRouterDemoModelClient(DemoModelClient):
    def __init__(self, settings: DemoAgentSettings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport
        self._tracer = get_tracer(__name__)

    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        trace_context: DemoTraceContext,
        workflow_id: str,
    ) -> DemoModelResponse:
        url = self._chat_completion_url()
        payload = self._payload(messages=messages, trace_context=trace_context, workflow_id=workflow_id)

        with self._tracer.start_as_current_span("llm.openrouter.chat_completion") as span:
            set_span_attributes(
                span,
                {
                    "llm.provider": "openrouter",
                    "llm.request.model": self._settings.demo_llm_model,
                    "demo.workflow_id": workflow_id,
                    "correlation_id": trace_context.correlation_id,
                    "request_id": trace_context.request_id,
                },
            )
            try:
                async with httpx.AsyncClient(
                    timeout=self._settings.demo_llm_timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = await client.post(url, headers=self._headers(), json=payload)
                    response.raise_for_status()
                    response_body = response.json()
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise DemoModelClientError(f"OpenRouter chat completion failed: {exc}") from exc

            model_response = _parse_openrouter_response(response_body)
            set_span_attributes(
                span,
                {
                    "llm.response.model": model_response.model,
                    "llm.response.id": model_response.generation_id,
                },
            )
            return model_response

    def _chat_completion_url(self) -> str:
        return f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str]:
        api_key = _non_empty(self._settings.openrouter_api_key)
        if api_key is None:
            raise DemoModelClientError("OPENROUTER_API_KEY is required for OpenRouter model calls")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        referer = _non_empty(self._settings.openrouter_http_referer)
        if referer is not None:
            headers["HTTP-Referer"] = referer
        app_title = _non_empty(self._settings.openrouter_app_title)
        if app_title is not None:
            headers["X-OpenRouter-Title"] = app_title
        return headers

    def _payload(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        trace_context: DemoTraceContext,
        workflow_id: str,
    ) -> dict[str, Any]:
        trace = {
            "trace_name": "demo-agent-reservation",
            "span_name": "agent.reason",
            "generation_name": "next-tool-selection",
        }
        if trace_context.trace_id is not None:
            trace["trace_id"] = trace_context.trace_id

        payload: dict[str, Any] = {
            "model": self._settings.demo_llm_model,
            "messages": [dict(message) for message in messages],
            "temperature": self._settings.demo_llm_temperature,
            "max_tokens": self._settings.demo_llm_max_tokens,
            "session_id": workflow_id,
            "metadata": {
                "workflow_id": workflow_id,
                "correlation_id": trace_context.correlation_id,
                "request_id": trace_context.request_id,
            },
            "trace": trace,
        }
        plugins = self._auto_router_plugins()
        if plugins:
            payload["plugins"] = plugins
        return payload

    def _auto_router_plugins(self) -> list[dict[str, Any]]:
        if self._settings.demo_llm_model != "openrouter/auto":
            return []

        plugin: dict[str, Any] = {"id": "auto-router"}
        allowed_models = _split_csv(self._settings.openrouter_allowed_models)
        if allowed_models:
            plugin["allowed_models"] = allowed_models
        if self._settings.openrouter_auto_cost_quality_tradeoff is not None:
            plugin["cost_quality_tradeoff"] = self._settings.openrouter_auto_cost_quality_tradeoff

        return [plugin] if len(plugin) > 1 else []


def build_demo_model_client(settings: DemoAgentSettings) -> DemoModelClient | None:
    provider = settings.demo_llm_provider.strip().lower()
    if provider in {"", "none", "disabled", "deterministic"}:
        return None
    if provider != "openrouter":
        raise DemoModelClientError(f"Unsupported demo LLM provider: {settings.demo_llm_provider}")
    if _non_empty(settings.openrouter_api_key) is None:
        return None
    return OpenRouterDemoModelClient(settings)


def _parse_openrouter_response(response_body: Any) -> DemoModelResponse:
    if not isinstance(response_body, dict):
        raise DemoModelClientError("OpenRouter response body was not an object")

    choices = response_body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise DemoModelClientError("OpenRouter response did not include choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise DemoModelClientError("OpenRouter first choice was not an object")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise DemoModelClientError("OpenRouter first choice did not include a message")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise DemoModelClientError("OpenRouter message content was empty")

    model = response_body.get("model")
    generation_id = response_body.get("id")
    return DemoModelResponse(
        content=content,
        model=model if isinstance(model, str) else None,
        generation_id=generation_id if isinstance(generation_id, str) else None,
    )


def _split_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
