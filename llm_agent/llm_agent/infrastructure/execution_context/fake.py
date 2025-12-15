import contextlib

import starlette.types
import structlog
from authlib.jose import jwt

from llm_agent.api.context.constants import REQUEST_ID_NAME, SCOPE_TYPE_NAME, JWT_TOKEN_NAME
from llm_agent.api.context.request import RequestContextVars
from llm_agent.application.execution_context import ExecutionContextEnricher
from llm_agent.infrastructure.execution_context.request_id import generate_request_id


def generate_fake_jwt_token() -> str:
    payload = {
        "sub": "1234567890",
        "name": "John Doe",
        "iat": 1516239022,
    }
    token = jwt.encode(payload=payload, key="secret", header={"alg": "HS256"})
    return token

class FakeExecutionContextEnricher(ExecutionContextEnricher):

    @contextlib.contextmanager
    def enrich_from_scope(self, scope: starlette.types.Scope):
        scope.setdefault("state", {})
        request_id = generate_request_id()
        scope_type = scope["type"]

        jwt_token = None
        if scope_type == "http":
            jwt_token = generate_fake_jwt_token()

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
        return receive