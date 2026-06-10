from __future__ import annotations

import pytest

from agent_run_worker.demo.mcp_client import DemoMcpClientError, FastMcpDemoToolClient, normalize_tool_result
from agent_run_worker.demo.trace_context import DemoTraceContext
from agent_run_worker.demo.types import DemoToolResult


def test_normalize_tool_result_keeps_dict_payload():
    result = normalize_tool_result("tool", {"ok": True})

    assert result == DemoToolResult(tool_name="tool", outcome="succeeded", payload={"ok": True})


@pytest.mark.asyncio
async def test_fast_mcp_client_rejects_non_allowlisted_tool():
    client = FastMcpDemoToolClient(settings=_settings())

    with pytest.raises(DemoMcpClientError):
        await client.call_tool("unknown_tool", {}, _trace_context(), fault="none")


def _settings():
    from agent_run_worker.demo.config import DemoAgentSettings

    return DemoAgentSettings(
        movie_reservation_mcp_url="http://movie-reservation-mcp:8091/mcp",
        axum_tools_mcp_url="http://axum-tools-mcp:8092/mcp",
    )


def _trace_context() -> DemoTraceContext:
    return DemoTraceContext(
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        correlation_id="corr-1",
        request_id="req-1",
        workflow_id="workflow-1",
    )
