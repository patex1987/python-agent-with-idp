from local_runtime.provider import create_default_local_shared_infrastructure
from tests.fake_implementations.agent_job_worker.di.registrars.consumer import ConsumerRegistrar
from tests.fake_implementations.llm_agent.di.registrars.auth import DevelopmentAuthRegistrar
from llm_agent.di.app_wide_registrar import ApplicationDIConfig
from llm_agent.di.registrars.game_state import GameStateRegistrar
from llm_agent.di.registrars.throttle_step_service import ThrottleStepsServiceRegistrar
from tests.fake_implementations.llm_agent.di.registrars.job_orchestrator import InMemoryJobOrchestrationRegistrar


def get_development_registrars() -> ApplicationDIConfig:
    """
    Registrars ensuring the service runs in local development mode.
    """

    shared_local_infrastructure = create_default_local_shared_infrastructure()

    fastapi_lifespan_registrars = [
        ThrottleStepsServiceRegistrar(),
        GameStateRegistrar(),
        InMemoryJobOrchestrationRegistrar(shared_local_infrastructure),
    ]
    app_lifetime_registrars = [DevelopmentAuthRegistrar()]

    infrastructure_registrars = [ConsumerRegistrar(shared_local_infrastructure)]

    app_registrars = ApplicationDIConfig(
        app_lifetime_registrars=app_lifetime_registrars,
        fastapi_lifespan_registrars=fastapi_lifespan_registrars,
        infrastructure_registrars=infrastructure_registrars,
    )
    return app_registrars
