"""
Protocol for extracting JWT tokens from ASGI scopes.
"""

from typing import Protocol

import starlette.types


class TokenExtractor(Protocol):
    """
    Protocol for extracting JWT tokens from ASGI request scopes.

    Different implementations handle token extraction from different sources:
    - HTTP requests: Extract from Authorization header
    - WebSocket connections: Extract from connection_init message payload
    """

    def extract_safe(self, scope: starlette.types.Scope) -> str | None:
        """
        Safely extract a JWT token from the ASGI scope.

        This method should not raise exceptions if the token is missing or malformed.
        It should return None in such cases to allow graceful handling.

        :param scope: ASGI scope dictionary
        :return: JWT token string if found, None otherwise
        """
        ...

