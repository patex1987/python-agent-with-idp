import svcs.fastapi

import fastapi

from llm_agent.di.registry_builder import apply_registrars
from llm_agent.domain.infrastructure_setup import InfrastructureSetup


async def di_lifespan(app: fastapi.FastAPI, registry: svcs.Registry):
    """
    FastAPI application lifespan responsible for wiring DI registrars and managing runtime infrastructure.

    This lifespan is invoked via ``svcs.fastapi.lifespan`` with an explicitly
    constructed ``svcs.Registry`` created at the composition root. The same registry
    is shared across middleware and business logic, ensuring consistent
    singleton instances (e.g. auth clients, configuration, infrastructure adapters).

    Responsibilities:
    - Apply FastAPI-lifespan-scoped DI registrars
    - Start and stop runtime infrastructure resources (e.g. database pools)

    Notes:
    - The ``@svcs.fastapi.lifespan`` decorator is intentionally not used; the lifespan
      is wrapped explicitly at application creation time to inject a pre-built registry.
    - This keeps dependency wiring explicit and avoids implicit registry creation.
    - For more complex lifecycle needs, this can be replaced with a fully custom
      FastAPI lifespan.

    :param app: The FastAPI application instance.
    :param registry: The shared ``svcs.Registry`` instance provided by the
        composition root and managed by ``svcs.fastapi.lifespan`
    """
    infra_setup: InfrastructureSetup = app.state.infrastructure_setup

    try:
        fastapi_lifespan_registrars = app.state.fastapi_lifespan_registrars
        apply_registrars(fastapi_lifespan_registrars, registry=registry)

        await infra_setup.setup()

        yield {"application": "throttling_calculator"}
    finally:
        await infra_setup.shutdown()
