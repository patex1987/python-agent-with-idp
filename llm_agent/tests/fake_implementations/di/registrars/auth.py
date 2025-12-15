import svcs

from tests.fake_implementations.infrastructure.auth.fake_manager import FakeAuthManager
from llm_agent.application.authentication.manager import AsyncAuthenticationManager
from llm_agent.application.execution_context import ExecutionContextEnricher
from llm_agent.di.registrars.base import Registrar
from llm_agent.infrastructure.execution_context.fake import FakeExecutionContextEnricher


class DevelopmentAuthRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        registry.register_factory(ExecutionContextEnricher, FakeExecutionContextEnricher)
        registry.register_value(AsyncAuthenticationManager, FakeAuthManager())
