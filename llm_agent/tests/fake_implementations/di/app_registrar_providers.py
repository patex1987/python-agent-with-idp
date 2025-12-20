from agent_job_worker.in_memory.consumer import InMemoryConsumer
from llm_agent.infrastructure.agent.in_memory.queue import InMemoryJobSignalQueue
from llm_agent.infrastructure.agent.in_memory.store import InMemoryJobProcessingStore
from tests.fake_implementations.di.factories.job_related import (
    InternalJobStorageProvider,
    InternalEventLogsProvider,
)
from tests.fake_implementations.di.registrars.auth import DevelopmentAuthRegistrar
from llm_agent.di.app_wide_registrar import ApplicationDIConfig
from llm_agent.di.registrars.game_state import GameStateRegistrar
from llm_agent.di.registrars.throttle_step_service import ThrottleStepsServiceRegistrar
from llm_agent.infrastructure.infra_setup.local_dev import LocalDevInfrastructureSetup
from tests.fake_implementations.di.registrars.job_orchestrator import InMemoryJobOrchestrationRegistrar


def get_development_registrars() -> ApplicationDIConfig:
    """
    Registrars ensuring the service runs in local development mode.

    TODO: create a separate DI registry for the infrastructure setup, avoid creating objects in place
    """
    fastapi_lifespan_registrars = [
        ThrottleStepsServiceRegistrar(),
        GameStateRegistrar(),
        InMemoryJobOrchestrationRegistrar(),
    ]
    app_lifetime_registrars = [DevelopmentAuthRegistrar()]

    in_memory_job_consumer = InMemoryConsumer(
        job_store=InMemoryJobProcessingStore(
            internal_job_storage=InternalJobStorageProvider.get_instance(),
            internal_event_logs=InternalEventLogsProvider.get_instance(),
        ),
        # TODO: this needs to share the state, otherwise notifications won't work
        job_signal_queue=InMemoryJobSignalQueue(),
        worker_id="worker-1",
    )

    app_registrars = ApplicationDIConfig(
        app_lifetime_registrars=app_lifetime_registrars,
        fastapi_lifespan_registrars=fastapi_lifespan_registrars,
        infrastructure_bootstrapper=LocalDevInfrastructureSetup(consumer=in_memory_job_consumer),
    )
    return app_registrars
