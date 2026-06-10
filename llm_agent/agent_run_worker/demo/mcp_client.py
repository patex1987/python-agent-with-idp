from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any, Protocol

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from opentelemetry.trace import Status, StatusCode

from agent_run_worker.demo.config import DemoAgentSettings
from agent_run_worker.demo.trace_context import DemoTraceContext
from agent_run_worker.demo.types import DemoToolMetadata, DemoToolResult
from llm_agent.core.telemetry import get_tracer, set_span_attributes

RECOMMENDATION_TOOL = "recommendation_get_movies"
MOVIE_TOOLS = {
    "movie_list_screenings",
    "movie_request_reservation",
    "movie_get_reservation_status",
    "movie_get_reservation_result",
}
REQUIRED_TOOLS = {RECOMMENDATION_TOOL, *MOVIE_TOOLS}


class DemoMcpClientError(RuntimeError):
    def __init__(self, message: str, *, tool_name: str | None = None) -> None:
        super().__init__(message)
        self.tool_name = tool_name


class DemoMcpToolClient(Protocol):
    async def list_available_tools(self, trace_context: DemoTraceContext) -> list[DemoToolMetadata]: ...

    async def call_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        trace_context: DemoTraceContext,
        *,
        fault: str,
    ) -> DemoToolResult: ...


class FastMcpDemoToolClient(DemoMcpToolClient):
    def __init__(self, settings: DemoAgentSettings) -> None:
        self._settings = settings
        self._tracer = get_tracer(__name__)

    async def list_available_tools(self, trace_context: DemoTraceContext) -> list[DemoToolMetadata]:
        tool_metadata: list[DemoToolMetadata] = []

        for server_name, url in self._server_urls().items():
            transport = StreamableHttpTransport(url, headers=trace_context.to_headers())
            try:
                async with Client(transport, timeout=self._settings.demo_mcp_timeout_seconds) as client:
                    tools = await client.list_tools()
            except Exception as exc:
                raise DemoMcpClientError(f"Unable to list tools from {server_name}: {exc}") from exc

            for tool in tools:
                tool_metadata.append(
                    DemoToolMetadata(
                        name=tool.name,
                        server_name=server_name,
                        description=tool.description,
                        input_schema=tool.inputSchema,
                    )
                )

        missing_tools = REQUIRED_TOOLS - {tool.name for tool in tool_metadata}
        if missing_tools:
            missing = ", ".join(sorted(missing_tools))
            raise DemoMcpClientError(f"Missing required MCP tools: {missing}")

        return tool_metadata

    async def call_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        trace_context: DemoTraceContext,
        *,
        fault: str,
    ) -> DemoToolResult:
        if tool_name not in REQUIRED_TOOLS:
            raise DemoMcpClientError(f"Tool {tool_name} is not allowlisted", tool_name=tool_name)

        server_name = self._server_name_for_tool(tool_name)
        url = self._server_urls()[server_name]
        merged_arguments = dict(arguments)
        merged_arguments.update(trace_context.to_tool_arguments(fault=fault))
        transport = StreamableHttpTransport(url, headers=trace_context.to_headers())

        with self._tracer.start_as_current_span(f"mcp.tool.{tool_name}") as span:
            set_span_attributes(
                span,
                {
                    "mcp.tool.name": tool_name,
                    "mcp.server.name": server_name,
                    "mcp.server.url": url,
                    "correlation_id": trace_context.correlation_id,
                    "request_id": trace_context.request_id,
                    "demo.fault": fault,
                },
            )

            try:
                async with asyncio.timeout(self._settings.demo_mcp_timeout_seconds):
                    async with Client(transport, timeout=self._settings.demo_mcp_timeout_seconds) as client:
                        result = await client.call_tool(
                            tool_name,
                            merged_arguments,
                            timeout=self._settings.demo_mcp_timeout_seconds,
                            meta=trace_context.to_tool_arguments(fault=fault),
                        )
            except TimeoutError as exc:
                message = f"MCP tool {tool_name} timed out"
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, message))
                return DemoToolResult(tool_name=tool_name, outcome="timeout", error=message)
            except Exception as exc:
                message = f"MCP tool {tool_name} failed: {exc}"
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, message))
                return DemoToolResult(tool_name=tool_name, outcome="failed", error=message)

        return normalize_tool_result(tool_name, result)

    def _server_urls(self) -> dict[str, str]:
        return {
            "movie_reservation": self._settings.movie_reservation_mcp_url,
            "axum_tools": self._settings.axum_tools_mcp_url,
        }

    @staticmethod
    def _server_name_for_tool(tool_name: str) -> str:
        if tool_name == RECOMMENDATION_TOOL:
            return "axum_tools"
        return "movie_reservation"


def normalize_tool_result(tool_name: str, result: Any) -> DemoToolResult:
    if isinstance(result, DemoToolResult):
        return result

    is_error = bool(getattr(result, "isError", False))
    payload = _extract_payload(result)
    outcome = "failed" if is_error else "succeeded"
    return DemoToolResult(tool_name=tool_name, outcome=outcome, payload=payload)


def _extract_payload(result: Any) -> Any:
    if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
        return result

    structured_content = getattr(result, "structuredContent", None)
    if structured_content is not None:
        return structured_content

    content = getattr(result, "content", None)
    if not content:
        return None

    extracted: list[Any] = []
    for item in content:
        text = getattr(item, "text", None)
        if text is None:
            extracted.append(item)
            continue

        try:
            extracted.append(json.loads(text))
        except json.JSONDecodeError:
            extracted.append(text)

    if len(extracted) == 1:
        return extracted[0]
    return extracted
