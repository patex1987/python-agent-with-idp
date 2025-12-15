from typing import Sequence

import svcs

from llm_agent.di.registrars.base import Registrar


def apply_registrars(registrars: Sequence[Registrar], registry: svcs.Registry | None = None):
    if not registry:
        registry = svcs.Registry()

    for registrar in registrars:
        registrar.register(registry)

    return registry
