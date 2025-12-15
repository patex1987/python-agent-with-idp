# TODO: move to a separate commit


import fastapi
import starlette.types

import structlog
from starlette import status

from llm_agent.api.context.constants import USER_ID_NAME, JWT_TOKEN_NAME
from llm_agent.application.authentication.manager import AsyncAuthenticationManager
from llm_agent.domain.authentication.exceptions import AuthenticationError

logger = structlog.get_logger(__name__)


class AuthenticationMiddleware:
    def __init__(self, app: fastapi.FastAPI, authentication_manager: AsyncAuthenticationManager):
        self.app = app
        self.authentication_manager = authentication_manager
        self.excluded_paths = ("/health",)

    async def __call__(
        self, scope: starlette.types.Scope, receive: starlette.types.Receive, send: starlette.types.Send
    ):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        raw_path = scope.get("path")
        if str(raw_path).startswith(self.excluded_paths):
            logger.debug("Auth validation skipped for health checks")
            return await self.app(scope, receive, send)

        try:
            extracted_token = scope["state"].get(JWT_TOKEN_NAME)
            user_identity = await self.authentication_manager.authenticate_jwt_token(extracted_token)
            structlog.contextvars.bind_contextvars(user_id=user_identity.user_id)
            scope["state"][USER_ID_NAME] = user_identity.user_id
        except AuthenticationError as e:
            logger.warning("Authentication failed", exc_info=e)
            response = fastapi.responses.JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication failed"},
            )
            await response(scope, receive, send)
            return
        except Exception as e:
            logger.error("Unexpected error during authentication", exc_info=e)
            response = fastapi.responses.JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Unexpected error during authentication"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
