from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers

CORRELATION_ID_NAME = "correlation_id"
REQUEST_ID_NAME = "request_id"
TRACEPARENT_NAME = "traceparent"
TRACESTATE_NAME = "tracestate"


@dataclass(frozen=True)
class DemoTraceContext:
    traceparent: str | None
    tracestate: str | None
    correlation_id: str
    request_id: str
    workflow_id: str

    @classmethod
    def from_headers(
        cls,
        *,
        headers: Headers,
        scope_state: dict[str, Any],
        current_traceparent: str | None,
    ) -> "DemoTraceContext":
        request_id = headers.get("x-request-id") or scope_state.get(REQUEST_ID_NAME) or str(uuid4())
        correlation_id = headers.get("x-correlation-id") or scope_state.get(CORRELATION_ID_NAME) or request_id
        traceparent = headers.get("traceparent") or scope_state.get(TRACEPARENT_NAME) or current_traceparent
        tracestate = headers.get("tracestate") or scope_state.get(TRACESTATE_NAME)
        return cls(
            traceparent=traceparent,
            tracestate=tracestate,
            correlation_id=correlation_id,
            request_id=request_id,
            workflow_id=str(uuid4()),
        )

    @property
    def trace_id(self) -> str | None:
        if not self.traceparent:
            return None

        parts = self.traceparent.split("-")
        if len(parts) < 4:
            return None

        trace_id = parts[1]
        if len(trace_id) != 32:
            return None
        return trace_id

    def to_headers(self) -> dict[str, str]:
        headers = {
            "X-Correlation-Id": self.correlation_id,
            "X-Request-Id": self.request_id,
        }
        if self.traceparent:
            headers["traceparent"] = self.traceparent
        if self.tracestate:
            headers["tracestate"] = self.tracestate
        return headers

    def to_tool_arguments(self, *, fault: str) -> dict[str, str]:
        arguments = {
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
            "demo_fault": fault,
        }
        if self.traceparent:
            arguments["traceparent"] = self.traceparent
        if self.tracestate:
            arguments["tracestate"] = self.tracestate
        return arguments

    def to_response_trace(self, trace_id: str | None = None) -> dict[str, str | None]:
        return {
            "trace_id": trace_id or self.trace_id,
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
        }
