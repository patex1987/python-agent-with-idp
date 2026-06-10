import contextlib
from functools import wraps

import starlette.types
from starlette.datastructures import Headers
import structlog

from llm_agent.api.context.constants import (
    CORRELATION_ID_NAME,
    JWT_TOKEN_NAME,
    REQUEST_ID_NAME,
    SCOPE_TYPE_NAME,
    TRACEPARENT_NAME,
    TRACESTATE_NAME,
)
from llm_agent.application.execution_context import ExecutionContextEnricher
from llm_agent.api.context.request import (
    RequestContextVars,
)
from llm_agent.infrastructure.execution_context.request_id import generate_request_id
from llm_agent.infrastructure.execution_context.token_extractors import (
    HttpTokenExtractor,
    WebSocketTokenExtractor,
)


class ProductionContextEnricher(ExecutionContextEnricher):
    """
    Production implementation of ExecutionContextEnricher.

    Enriches request execution context with:
    - Request IDs for tracing
    - JWT tokens extracted from HTTP headers or WebSocket connection_init messages
    - Structured logging context variables

    This implementation uses token extractors to safely extract JWT tokens from
    different request types (HTTP vs WebSocket) and stores them in both scope state
    and context variables for request-scoped access.
    """

    def __init__(
        self,
        http_token_extractor: HttpTokenExtractor,
        websocket_token_extractor: WebSocketTokenExtractor,
    ):
        """
        :param http_token_extractor: Extractor for JWT tokens from HTTP requests
        :param websocket_token_extractor: Extractor for JWT tokens from WebSocket connections
        """
        self.http_token_extractor = http_token_extractor
        self.websocket_token_extractor = websocket_token_extractor

    @contextlib.contextmanager
    def enrich_from_scope(self, scope: starlette.types.Scope):
        scope.setdefault("state", {})
        scope_type = scope["type"]
        headers = Headers(scope=scope) if scope_type == "http" else Headers(raw=[])
        request_id = headers.get("x-request-id") or generate_request_id()
        correlation_id = headers.get("x-correlation-id") or request_id
        traceparent = headers.get("traceparent")
        tracestate = headers.get("tracestate")

        jwt_token = None
        if scope_type == "http":
            jwt_token = self.http_token_extractor.extract_safe(scope)

        structlog_context = {
            REQUEST_ID_NAME: request_id,
            CORRELATION_ID_NAME: correlation_id,
            SCOPE_TYPE_NAME: scope_type,
        }
        if traceparent:
            structlog_context[TRACEPARENT_NAME] = traceparent

        try:
            structlog.contextvars.bind_contextvars(**structlog_context)
            RequestContextVars.JWT_TOKEN.set(jwt_token)
            RequestContextVars.REQUEST_ID.set(request_id)
            RequestContextVars.CORRELATION_ID.set(correlation_id)
            RequestContextVars.TRACEPARENT.set(traceparent)
            RequestContextVars.TRACESTATE.set(tracestate)
            scope["state"][REQUEST_ID_NAME] = request_id
            scope["state"][CORRELATION_ID_NAME] = correlation_id
            scope["state"][TRACEPARENT_NAME] = traceparent
            scope["state"][TRACESTATE_NAME] = tracestate
            scope["state"][JWT_TOKEN_NAME] = jwt_token
            yield
        finally:
            structlog.contextvars.clear_contextvars()
            RequestContextVars.JWT_TOKEN.set(None)
            RequestContextVars.REQUEST_ID.set(None)
            RequestContextVars.CORRELATION_ID.set(None)
            RequestContextVars.TRACEPARENT.set(None)
            RequestContextVars.TRACESTATE.set(None)

    def get_instrumented_send(self, send: starlette.types.Send, scope: starlette.types.Scope, custom_attributes: dict):
        """
        Not used at the moment, but can be used to enrich the headers for outgoing requests
        """
        return send

    def get_instrumented_receive(
        self, receive: starlette.types.Receive, scope: starlette.types.Scope, custom_attributes: dict
    ):
        @wraps(receive)
        async def instrumented_receive() -> starlette.types.Message:
            message = await receive()

            jwt_token = self.websocket_token_extractor.extract_safe(message)
            if not jwt_token:
                return message

            RequestContextVars.JWT_TOKEN.set(jwt_token)
            scope["state"][JWT_TOKEN_NAME] = jwt_token

            return message

        return instrumented_receive
