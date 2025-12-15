import fastapi
import svcs

from throttling_sequencer.api.http.middlewares.authentication import (
    AuthenticationMiddleware,
)
from throttling_sequencer.api.http.middlewares.execution import ExecutionContextMiddleware
from throttling_sequencer.api.http.v1.routes.health import health_router
from throttling_sequencer.api.http.v1.routes.throttle_steps_calculator import throttle_router
from throttling_sequencer.application.authentication.manager import AsyncAuthenticationManager
from throttling_sequencer.application.execution_context import ExecutionContextEnricher
from throttling_sequencer.core.log_config import configure_logging
from throttling_sequencer.core.telemetry import instrument_for_telemetry
from throttling_sequencer.di.fastapi_lifespan import di_lifespan
from throttling_sequencer.infrastructure.db.piccolo_throttling_sequencer_app.programmatic_migration import maybe_migrate


def create_app(*, registry: svcs.Registry) -> fastapi.FastAPI:
    """
    Construct the FastAPI application using an explicitly provided DI registry.

    The application lifespan is wrapped with ``svcs.fastapi.lifespan`` to ensure
    that the given registry is used consistently for dependency resolution and
    properly managed for startup and shutdown.
    """
    configure_logging()
    svcs_lifespan = svcs.fastapi.lifespan(di_lifespan, registry=registry)
    app = fastapi.FastAPI(lifespan=svcs_lifespan)

    app.include_router(router=health_router, prefix="/api/v1/health", tags=["health"])
    app.include_router(router=throttle_router, prefix="/api/v1/throttle", tags=["throttle"])

    instrument_for_telemetry(app)

    # app.add_exception_handler(Exception, exception_handler)
    # app.add_exception_handler(500, exception_handler)

    maybe_migrate()

    return app


def register_middlewares(app: fastapi.FastAPI, di_container: svcs.Container) -> None:
    """
    Register FastAPI middleware components.

    Middleware is initialized using a container derived from the same DI registry
    as the rest of the application, ensuring consistent access to shared
    dependencies (e.g. authentication, request context, logging).
    """
    app.add_middleware(AuthenticationMiddleware, authentication_manager=di_container.get(AsyncAuthenticationManager))
    app.add_middleware(ExecutionContextMiddleware, execution_context_enricher=di_container.get(ExecutionContextEnricher))
