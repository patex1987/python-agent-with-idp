from typing import Sequence

from tests.fake_implementations.di.app_registrar_providers import get_development_registrars
from llm_agent.di.app_wide_registrar import ApplicationDIConfig
from llm_agent.di.provider import RegistrarProvider
from llm_agent.di.registrars.base import Registrar


class ComposableRegistrarProvider(RegistrarProvider):
    """
    Registrar provider that extends a base configuration with additional registrars.

    This provider is designed for testing scenarios  where one needs to customize
    the dependency injection configuration by adding test-specific registrars
    (e.g., mocks, fakes, or test doubles) on top of a base development
    configuration.

    The additional registrars are prepended to the base registrars, allowing test
    registrars to override base registrations when the same types are registered.

    :param app_lifetime_registrars: Additional registrars to prepend to the base
        app_lifetime_registrars. These are applied synchronously at application startup.
    :param fastapi_lifespan_registrars: Additional registrars to prepend to the base
        fastapi_lifespan_registrars. These are applied during the FastAPI lifespan.

    Example:

        provider = ComposableRegistrarProvider(
            app_lifetime_registrars=[MockAuthClientRegistrar()],
            fastapi_lifespan_registrars=[TestRepositoryRegistrar()]
        )
        app = create_app_with_selected_di(provider)
    """

    def __init__(
        self,
        app_lifetime_registrars: Sequence[Registrar],
        fastapi_lifespan_registrars: Sequence[Registrar],
    ):
        self.base_provider = get_development_registrars
        self.app_lifetime_registrars = app_lifetime_registrars
        self.fastapi_lifespan_registrars = fastapi_lifespan_registrars

    def __call__(self) -> ApplicationDIConfig:
        base_config = self.base_provider()
        return ApplicationDIConfig(
            app_lifetime_registrars=self.app_lifetime_registrars + base_config.app_lifetime_registrars,
            fastapi_lifespan_registrars=self.fastapi_lifespan_registrars + base_config.fastapi_lifespan_registrars,
            infrastructure_bootstrapper=base_config.infrastructure_bootstrapper,
        )
