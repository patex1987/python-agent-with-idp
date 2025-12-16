"""
Authlib-based token validation client for OpenID Connect identity providers.
"""

import httpx

from authlib.jose import jwt
from authlib.jose.errors import DecodeError, InvalidClaimError, ExpiredTokenError, InvalidTokenError
from authlib.oidc.discovery import get_well_known_url

from llm_agent.application.authentication.token_validation_client import (
    TokenValidationClient,
)
from llm_agent.domain.authentication.exceptions import AuthenticationError


class JWTValidationClient(TokenValidationClient):
    """
    Token validation client using authlib library.

    Communicates with OpenID Connect identity providers (Keycloak, Microsoft Entra, etc.)
    to validate JWT tokens by fetching JWKS keys and metadata.

    Note: theoretically you can add ttl, size limit to _metadata_cache to avoid explosion.
    """

    def __init__(self):
        # One client = shared connection pool + JWKS cache
        # self._client = AsyncOAuth2Client(timeout=5.0)
        self._client = httpx.AsyncClient(timeout=5.0)
        self._metadata_cache: dict[str, dict] = {}
        self._jwks_cache: dict[str, dict] = {}

    async def authenticate(
        self,
        token: str,
        audience: list[str],
        oidc_discovery_url: str,
    ) -> dict:
        """
        Validate a JWT token using OpenID Connect discovery and JWKS.
        """
        metadata = await self._get_oidc_metadata(oidc_discovery_url)
        jwks = await self._get_jwks(metadata["jwks_uri"])

        try:
            key_loader = self._build_key_loader(jwks)
            claims = jwt.decode(
                token,
                key=key_loader,
                claims_options={
                    "iss": {"essential": True, "value": metadata["issuer"]},
                    # "aud": {"essential": True, "values": audience},
                    "exp": {"essential": True},
                },
            )
            claims.validate()
            return dict(claims)

        except (DecodeError, InvalidClaimError, ExpiredTokenError, InvalidTokenError) as e:
            raise AuthenticationError("Token validation failed") from e

    async def _get_oidc_metadata(self, issuer: str) -> dict:
        """Fetch and cache OpenID Connect metadata from the issuer."""
        if issuer not in self._metadata_cache:
            url = get_well_known_url(issuer, external=True)
            resp = await self._client.get(url)
            resp.raise_for_status()
            self._metadata_cache[issuer] = resp.json()
        return self._metadata_cache[issuer]

    async def _get_jwks(self, jwks_uri: str) -> dict:
        if jwks_uri not in self._jwks_cache:
            resp = await self._client.get(jwks_uri)
            resp.raise_for_status()
            self._jwks_cache[jwks_uri] = resp.json()
        return self._jwks_cache[jwks_uri]

    def _build_key_loader(self, jwks: dict):
        """
        Build a synchronous key loader for Authlib.
        """

        keys_by_kid = {key["kid"]: key for key in jwks.get("keys", []) if "kid" in key}

        def load_key(header, payload):
            kid = header.get("kid")
            if not kid or kid not in keys_by_kid:
                raise AuthenticationError(f"Unknown key id: {kid}")
            return keys_by_kid[kid]

        return load_key
