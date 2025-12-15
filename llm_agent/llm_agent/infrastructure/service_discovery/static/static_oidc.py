"""
Static OpenID Connect configuration provider.
"""

from llm_agent.application.authentication.oidc_configuration_provider import (
    OpenIdConfigurationProvider,
)
from llm_agent.domain.authentication.oidc_configuration import (
    OpenIdConfiguration,
)


class StaticOpenIdConfigurationProvider(OpenIdConfigurationProvider):
    """
    Static configuration provider for OpenID Connect settings.

    This is a simple implementation that returns fixed configuration values.
    In production, this should be replaced with a service discovery-based implementation
    that extracts OIDC configuration from service discovery output.

    discovery url example: http://localhost:8082/realms/throttling-test
    """

    def __init__(self, *, realm_name: str, discovery_url: str):
        self._config = OpenIdConfiguration(
            realm_name=realm_name,
            openid_discovery_url=discovery_url,
        )

    async def __call__(self) -> OpenIdConfiguration:
        """Return the static OpenID Connect configuration."""
        return self._config
