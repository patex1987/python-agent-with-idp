from typing import Protocol

import svcs


class Registrar(Protocol):
    def register(self, registry: svcs.Registry) -> None: ...
