from typing import Protocol

from llm_agent.di.app_wide_registrar import ApplicationDIConfig


class RegistrarProvider(Protocol):
    def __call__(self) -> ApplicationDIConfig: ...
