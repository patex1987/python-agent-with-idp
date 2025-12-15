from dataclasses import dataclass
from typing import Sequence

from llm_agent.di.registrars.base import Registrar
from llm_agent.domain.infrastructure_setup import InfrastructureSetup


@dataclass
class ApplicationDIConfig:
    """
    Configuration container for dependency injection registrars and infrastructure setup.

    This class organizes DI registrars by their application lifecycle phase and provides
    infrastructure bootstrapping configuration. Registrars are objects that register
    service dependencies into an ``svcs.Registry``.

    All registrars are applied to the same shared registry, but the distinction between
    ``app_lifetime_registrars`` and ``fastapi_lifespan_registrars`` reflects when they
    are registered in the application lifecycle.

    :param app_lifetime_registrars: Registrars applied synchronously at application startup,
        before middleware registration. These dependencies must be available immediately
        for middleware initialization (e.g., Keycloak clients, service discovery clients).
        The container created from these registrars is passed to ``register_middlewares()``
        to ensure middleware has access to these dependencies at registration time.
    :param fastapi_lifespan_registrars: Registrars applied asynchronously during the FastAPI
        application lifespan (after startup, before shutdown). These are registered when
        the lifespan context manager enters. Use these for dependencies that can be
        registered asynchronously or that depend on infrastructure resources initialized
        during lifespan (e.g., database repositories that depend on connection pools).
    :param infrastructure_bootstrapper: Infrastructure setup handler that manages
        lifecycle of infrastructure resources (e.g., database connection pools).
        Its ``setup()`` method is called during lifespan startup, and ``shutdown()``
        is called during lifespan teardown.
    """

    app_lifetime_registrars: Sequence[Registrar]
    fastapi_lifespan_registrars: Sequence[Registrar]
    infrastructure_bootstrapper: InfrastructureSetup
