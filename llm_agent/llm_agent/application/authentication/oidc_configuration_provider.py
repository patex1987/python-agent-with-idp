from typing import Protocol

from llm_agent.domain.authentication.oidc_configuration import OpenIdConfiguration


class OpenIdConfigurationProvider(Protocol):
    """
    Protocol for providers that supply OpenID Connect configuration.

    This abstraction allows different implementations to provide OIDC configuration
    (realm name, discovery URL) from various sources (static config, service discovery, etc.).
    """

    async def __call__(self) -> OpenIdConfiguration:
        """
        Retrieve OpenID Connect configuration.

        :return: OpenIdConfiguration containing realm name and discovery URL
        """
        ...
