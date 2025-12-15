from typing import Protocol

from llm_agent.domain.authentication.user import AuthenticatedUser


class AsyncAuthenticationManager(Protocol):
    async def authenticate_jwt_token(self, token: str | None) -> AuthenticatedUser: ...
