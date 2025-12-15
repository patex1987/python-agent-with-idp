import contextlib
from functools import wraps

import starlette.types
import structlog

from llm_agent.api.context.constants import REQUEST_ID_NAME, SCOPE_TYPE_NAME, JWT_TOKEN_NAME
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
        request_id = generate_request_id()
        scope_type = scope["type"]

        jwt_token = None
        if scope_type == "http":
            jwt_token = self.http_token_extractor.extract_safe(scope)

        structlog_context = {
            REQUEST_ID_NAME: request_id,
            SCOPE_TYPE_NAME: scope_type,
        }

        try:
            structlog.contextvars.bind_contextvars(**structlog_context)
            RequestContextVars.JWT_TOKEN.set(jwt_token)
            scope["state"][REQUEST_ID_NAME] = request_id
            scope["state"][JWT_TOKEN_NAME] = jwt_token
            yield
        finally:
            structlog.contextvars.clear_contextvars()
            RequestContextVars.JWT_TOKEN.set(None)

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
