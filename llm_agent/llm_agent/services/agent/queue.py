from __future__ import annotations

from typing import Protocol


class JobSignalQueue(Protocol):
    async def wait(self, timeout: None | float = None) -> None: ...

    async def notify(self) -> None: ...
