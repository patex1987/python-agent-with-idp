from llm_agent.di.app_wide_registrar import ApplicationDIConfig
from llm_agent.di.registrars.auth import ProdAuthRegistrar
from llm_agent.di.registrars.game_state import GameStateRegistrar
from llm_agent.di.registrars.throttle_step_service import ThrottleStepsServiceRegistrar
from llm_agent.infrastructure.infra_setup.production import ProductionInfrastructureSetup


def get_production_registrars() -> ApplicationDIConfig:
    fastapi_lifespan_registrars = [ThrottleStepsServiceRegistrar(), GameStateRegistrar()]
    app_lifetime_registrars = [ProdAuthRegistrar()]
    app_wide_registrars = ApplicationDIConfig(
        app_lifetime_registrars=app_lifetime_registrars,
        fastapi_lifespan_registrars=fastapi_lifespan_registrars,
        infrastructure_bootstrapper=ProductionInfrastructureSetup(),
    )

    return app_wide_registrars
