from dataclasses import dataclass


@dataclass(frozen=True)
class OpenIdConfiguration:
    """OpenID Connect configuration containing realm and discovery URL."""

    realm_name: str
    openid_discovery_url: str
