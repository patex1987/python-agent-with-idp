from __future__ import annotations

from typing import Protocol, AsyncIterator
from uuid import UUID

from contracts.domain.runs.event import RunEvent


class RunNotifier(Protocol):
    async def publish(self, evt: RunEvent) -> None: ...

    async def subscribe(self, run_id: UUID) -> AsyncIterator[RunEvent]: ...
