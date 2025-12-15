from tests.fake_implementations.di.registrars.auth import DevelopmentAuthRegistrar
from llm_agent.di.app_wide_registrar import ApplicationDIConfig
from llm_agent.di.registrars.game_state import GameStateRegistrar
from llm_agent.di.registrars.throttle_step_service import ThrottleStepsServiceRegistrar
from llm_agent.infrastructure.infra_setup.local_dev import LocalDevInfrastructureSetup


def get_development_registrars() -> ApplicationDIConfig:
    fastapi_lifespan_registrars = [ThrottleStepsServiceRegistrar(), GameStateRegistrar()]
    app_lifetime_registrars = [DevelopmentAuthRegistrar()]
    app_registrars = ApplicationDIConfig(
        app_lifetime_registrars=app_lifetime_registrars,
        fastapi_lifespan_registrars=fastapi_lifespan_registrars,
        infrastructure_bootstrapper=LocalDevInfrastructureSetup(),
    )
    return app_registrars
