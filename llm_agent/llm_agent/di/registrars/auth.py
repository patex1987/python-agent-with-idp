import svcs
from pycparser.ply.yacc import Production

from llm_agent.application.authentication.manager import AsyncAuthenticationManager
from llm_agent.application.authentication.oidc_configuration_provider import OpenIdConfigurationProvider
from llm_agent.application.authentication.token_validation_client import TokenValidationClient
from llm_agent.application.execution_context import ExecutionContextEnricher
from llm_agent.di.registrars.base import Registrar
from llm_agent.infrastructure.authentication.jwt_manager import JwtAuthenticationManager
from llm_agent.infrastructure.authentication.jwt_validator import JWTValidationClient
from llm_agent.infrastructure.execution_context.production import ProductionContextEnricher
from llm_agent.infrastructure.execution_context.token_extractors import HttpTokenExtractor, WebSocketTokenExtractor
from llm_agent.infrastructure.service_discovery.static.static_oidc import StaticOpenIdConfigurationProvider


class ProdAuthRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        openid_conf_provider = self.__class__.create_openid_conf_provider()
        token_validation_client = self.__class__.create_token_validation_client()

        registry.register_value(OpenIdConfigurationProvider, openid_conf_provider)
        registry.register_value(TokenValidationClient, token_validation_client)

        auth_manager = JwtAuthenticationManager(
            token_validation_client=token_validation_client,
            openid_configuration_provider=openid_conf_provider,
        )
        registry.register_value(AsyncAuthenticationManager, auth_manager)

        context_enricher = self.__class__.create_enricher()
        registry.register_value(ExecutionContextEnricher, context_enricher)

    @classmethod
    def create_openid_conf_provider(cls) -> OpenIdConfigurationProvider:
        """
        # TODO: make service discovery better and not hardcoded (use files and env vars for the static one at least)
        """
        openid_conf_provider = StaticOpenIdConfigurationProvider(
            realm_name="throttling_test",
            discovery_url="http://localhost:8082/realms/throttling-test",
        )
        return openid_conf_provider

    @classmethod
    def create_token_validation_client(cls) -> TokenValidationClient:
        token_validation_client = JWTValidationClient()
        return token_validation_client

    @classmethod
    def create_enricher(cls) -> ExecutionContextEnricher:
        """
        TODO: move to classes instead of instances of extractors
        """
        context_enricher = ProductionContextEnricher(
            http_token_extractor=HttpTokenExtractor(),
            websocket_token_extractor=WebSocketTokenExtractor(),
        )
        return context_enricher
