import importlib
import os

import fastapi
import svcs
from fastapi import FastAPI

from contracts.services.consumer import Consumer
from llm_agent.app import create_app, register_middlewares
from llm_agent.di.app_wide_registrar import ApplicationDIConfig
from llm_agent.di.provider import RegistrarProvider
from llm_agent.di.registry_builder import apply_registrars
from llm_agent.domain.infrastructure_setup import InfrastructureSetup
from llm_agent.infrastructure.infra_setup.local_dev import LocalDevInfrastructureSetup


def compose_fastapi_app_with_registrars() -> fastapi.FastAPI:
    """
    Application composition root.

    Selects the DI registrar provider based on environment configuration and
    constructs the FastAPI application with the corresponding dependency wiring.

    This is the primary entrypoint for creating the application and is the only
    place where environment-specific composition decisions are made.
    """

    configured_registrar_provider_path = os.getenv(
        "DI_REGISTRAR_PROVIDER", "llm_agent.di.app_registrar_providers.get_production_registrars"
    )
    module_name, function_name = configured_registrar_provider_path.rsplit(".", 1)
    registrar_provider = getattr(importlib.import_module(module_name), function_name)
    app = create_app_with_selected_di(registrar_provider)
    return app


def create_app_with_selected_di(
    registrar_provider: RegistrarProvider,
) -> fastapi.FastAPI:
    """
    Create a FastAPI application using the provided DI registrar provider.

    This function constructs a single ``svcs.Registry`` that is shared across
    application middleware and business logic, ensuring consistent
    singleton instances throughout the application.

    The registry is populated in two phases:
    - application-lifetime registrars, applied at startup
    - FastAPI-lifespan registrars, applied during the application lifespan

    Middleware is initialized using a container derived from the same registry
    to guarantee alignment between middleware and business logic dependencies.
    """
    main_registry = svcs.Registry()
    app = create_app(registry=main_registry)
    app_registrars = registrar_provider()

    app_scoped_registry = apply_registrars(app_registrars.app_lifetime_registrars, main_registry)
    app_scoped_container = svcs.Container(app_scoped_registry)

    app.state.fastapi_lifespan_registrars = app_registrars.fastapi_lifespan_registrars

    infra_setup = build_infra_setup(app, app_registrars)
    app.state.infrastructure_setup = infra_setup

    register_middlewares(app, app_scoped_container)

    return app


def build_infra_setup(app: FastAPI, app_registrars: ApplicationDIConfig) -> InfrastructureSetup:
    """
    TODO: move this elsewhere
    :param app:
    :param app_registrars:
    :return:
    """
    infrastructure_registry = svcs.Registry()
    infra_registry = apply_registrars(app_registrars.infrastructure_registrars, infrastructure_registry)
    infra_container = svcs.Container(infra_registry)
    app.state.infrastructure_container = infra_container
    infra_setup = LocalDevInfrastructureSetup(consumer=infra_container.get(Consumer))
    return infra_setup
