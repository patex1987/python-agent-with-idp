from typing import Protocol


class TokenValidationClient(Protocol):
    """
    Protocol for token validation clients that communicate with identity providers.

    This abstraction allows different implementations (Keycloak, Microsoft Entra, etc.)
    to validate JWT tokens by fetching keys and metadata from the identity provider.
    """

    async def authenticate(
        self,
        token: str,
        audience: list[str],
        oidc_discovery_url: str,
    ) -> dict:
        """
        Validate a JWT token against the identity provider's public keys.

        :param token: The JWT token to validate
        :param audience: List of expected audience values
        :param oidc_discovery_url: The OpenID Connect discovery URL (issuer)
        :return: The validated token claims as a dictionary
        :raises: AuthenticationError if token is invalid or expired
        """
        ...
