import contextlib
from typing import Protocol

import starlette.types


class ExecutionContextEnricher(Protocol):
    """
    Protocol for enriching request execution context with metadata and state.

    Responsible for:
    - Extracting and setting request-scoped context variables (e.g., JWT
        tokens, request IDs) - used for telemetry and business purposes
    - Binding structured logging context variables

    This protocol enables dependency injection of different context enrichment strategies
    (e.g., production vs. test implementations) while maintaining a consistent interface.
    """

    @contextlib.contextmanager
    def enrich_from_scope(self, scope: starlette.types.Scope):
        """
        Enrich execution context from ASGI scope.

        This context manager extracts context information from the ASGI scope
        (e.g., request ID, JWT token) and binds it to context variables for the
        duration of the request lifecycle.

        :param scope: ASGI scope dictionary containing request metadata
        :yields: None (context manager for resource management)
        """
        ...

    def get_instrumented_send(self, send: starlette.types.Send, scope: starlette.types.Scope, custom_attributes: dict):
        """
        Create an instrumented send handler for outgoing messages.

        This method wraps the original send handler to enable context propagation
        or enrichment of outgoing messages (e.g., adding headers, logging).

        :param send: Original ASGI send callable
        :param scope: ASGI scope dictionary
        :param custom_attributes: Additional attributes to include in instrumentation
        :return: Instrumented send callable
        """
        ...

    def get_instrumented_receive(
        self, receive: starlette.types.Receive, scope: starlette.types.Scope, custom_attributes: dict
    ):
        """
        Create an instrumented receive handler for incoming messages.

        This method wraps the original receive handler to enable context extraction
        or enrichment of incoming messages (e.g., extracting tokens from WebSocket
        connection_init messages).

        :param receive: Original ASGI receive callable
        :param scope: ASGI scope dictionary
        :param custom_attributes: Additional attributes to include in instrumentation
        :return: Instrumented receive callable
        """
        ...
