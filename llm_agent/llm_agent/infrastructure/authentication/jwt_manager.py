"""
JWT-based authentication manager implementation.
"""

from llm_agent.application.authentication.manager import AsyncAuthenticationManager
from llm_agent.application.authentication.oidc_configuration_provider import (
    OpenIdConfigurationProvider,
)
from llm_agent.application.authentication.token_validation_client import (
    TokenValidationClient,
)
from llm_agent.domain.authentication.user import AuthenticatedUser
from llm_agent.infrastructure.authentication.keycloak_claims_parser import (
    parse_keycloak_claims,
)


class JwtAuthenticationManager(AsyncAuthenticationManager):
    """
    JWT token-based authentication manager.

    Orchestrates token validation using a TokenValidationClient and retrieves
    OpenID Connect configuration from an OpenIdConfigurationProvider.
    """

    def __init__(
        self,
        token_validation_client: TokenValidationClient,
        openid_configuration_provider: OpenIdConfigurationProvider,
    ):
        self.token_validation_client = token_validation_client
        self.openid_configuration_provider = openid_configuration_provider

    async def authenticate_jwt_token(self, token: str | None) -> AuthenticatedUser:
        """
        Authenticate a JWT token and return an AuthenticatedUser.

        :param token: The JWT token to authenticate
        :return: AuthenticatedUser with user information extracted from token claims
        :raises: PermissionError if token is missing or invalid
        """
        if not token:
            raise PermissionError("Missing token")

        oidc_config = await self.openid_configuration_provider()
        claims = await self.token_validation_client.authenticate(
            token,
            audience=["fill-in"],  # TODO: configure from environment/config
            oidc_discovery_url=oidc_config.openid_discovery_url,
        )

        return parse_keycloak_claims(claims)
