"""
Token extractor implementations for HTTP and WebSocket requests.
"""

import json

import starlette.types
import starlette.datastructures
import structlog
from fastapi.security.utils import get_authorization_scheme_param


logger = structlog.get_logger(__name__)


class InvalidHeaderError(Exception):
    pass


class HttpTokenExtractor:
    """
    Extracts JWT tokens from HTTP request Authorization headers.

    Supports Bearer token scheme: "Authorization: Bearer <token>"
    """

    @classmethod
    def extract(cls, scope: starlette.types.Scope) -> str:
        headers = starlette.datastructures.Headers(scope=scope)
        if not (auth_header := headers.get("Authorization")):
            raise InvalidHeaderError("Authorization header not found")

        scheme, token = get_authorization_scheme_param(auth_header)
        if not scheme:
            raise InvalidHeaderError("Malformed Authorization header")

        if scheme.lower() != "bearer":
            raise InvalidHeaderError(f"Unsupported scheme: {scheme}")

        return token

    @classmethod
    def extract_safe(cls, scope: starlette.types.Scope) -> str | None:
        """
        Extract JWT token from HTTP Authorization header.

        :param scope: ASGI scope dictionary
        :return: JWT token if found in Authorization header, None otherwise
        """
        try:
            return cls.extract(scope)
        except InvalidHeaderError as exc:
            logger.warning("Token extracting failed, suppressing", exc_type=exc.__class__.__name__)
            return None


class InvalidWebsocketAuthException(Exception):
    pass


class WebSocketTokenExtractor:
    """
    Extracts JWT tokens from WebSocket connection_init messages.

    For WebSocket connections, tokens are typically sent in the connection_init
    message payload as:
    ```
    {
        "type": "websocket.receive",
        "bytes": None,
        "text": "{\"type\":\"connection_init\",\"payload\":{\"Authorization\":\"Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTYiLCJpc3MiOiJodHRwczovL2tleWNsb2FrLmV4YW1wbGUuY29tL3JlYWxtcy9teS1yZWFsbSIsImF1ZCI6Im15LWNsaWVudCIsImV4cCI6MTczNTAwMDAwMH0.signature\"}}"
    }

    ```

    """

    @classmethod
    def extract_from_message(cls, message: starlette.types.Message) -> str | None:
        """
        Extract JWT token from WebSocket connection_init message.

        Parses the connection_init message payload to extract the authorization token,
        stores it in scope state for later retrieval, and returns it.

        :param message: ASGI WebSocket message
        :return: JWT token if found in connection_init payload, None otherwise
        """
        if message.get("type") != "websocket.receive":
            return None

        if not (raw_text := message.get("text")):
            return None

        try:
            parsed_data = json.loads(raw_text)
        except json.JSONDecodeError:
            return None

        if parsed_data.get("type") != "connection_init":
            return None

        authorization_data = parsed_data.get("payload", {}).get("authorization")
        scheme, token = get_authorization_scheme_param(authorization_data)
        if scheme.lower() != "bearer":
            raise InvalidWebsocketAuthException(f"Unsupported scheme: {scheme}")

        return token

    @classmethod
    def extract_safe(cls, message: starlette.types.Message) -> str | None:
        """
        Extract JWT token from WebSocket connection_init message stored in scope state.

        This method retrieves a token that was previously extracted and stored in scope state
        by calling extract_from_message. Use extract_from_message to extract from a message.

        :param message: websocket
        :return: JWT token if found in scope state, None otherwise
        """
        try:
            token = cls.extract_from_message(message)
            return token
        except InvalidWebsocketAuthException as exc:
            logger.warning("Token extracting failed, suppressing", exc_type=exc.__class__.__name__)
            return None
