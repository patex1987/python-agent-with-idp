from llm_agent.application.authentication.manager import AsyncAuthenticationManager
from llm_agent.domain.authentication.user import AuthenticatedUser


class FakeAuthManager(AsyncAuthenticationManager):
    async def authenticate_jwt_token(self, token: str | None) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id="test_user_id_1",
            username="main_admin_user",
            email="main@company.xyz",
            roles=["admin"],
            scopes=["read", "write"],
        )
