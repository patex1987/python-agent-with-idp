from llm_agent.di.app_wide_registrar import ApplicationDIConfig
from llm_agent.di.registrars.auth import ProdAuthRegistrar
from llm_agent.di.registrars.game_state import GameStateRegistrar
from llm_agent.di.registrars.run_orchestration import RunOrchestrationRegistrar
from llm_agent.di.registrars.throttle_step_service import ThrottleStepsServiceRegistrar


def get_production_registrars() -> ApplicationDIConfig:
    fastapi_lifespan_registrars = [ThrottleStepsServiceRegistrar(), GameStateRegistrar(), RunOrchestrationRegistrar()]
    app_lifetime_registrars = [ProdAuthRegistrar()]
    app_wide_registrars = ApplicationDIConfig(
        app_lifetime_registrars=app_lifetime_registrars,
        fastapi_lifespan_registrars=fastapi_lifespan_registrars,
        # TODO: tbd
        infrastructure_registrars=[],
    )

    return app_wide_registrars
