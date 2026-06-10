"""
Request-scoped context variables for storing execution context state.

These context variables use Python's contextvars module to provide thread-safe,
request-scoped storage that is automatically isolated per request/async task.
"""

import contextvars


class RequestContextVars:
    """
    Container for request-scoped context variables.

    These variables are automatically isolated per request/async task using
    Python's contextvars, ensuring thread-safe access to request-scoped state.
    """

    JWT_TOKEN: contextvars.ContextVar[str | None] = contextvars.ContextVar("jwt_token", default=None)
    REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
    CORRELATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)
    TRACEPARENT: contextvars.ContextVar[str | None] = contextvars.ContextVar("traceparent", default=None)
    TRACESTATE: contextvars.ContextVar[str | None] = contextvars.ContextVar("tracestate", default=None)
