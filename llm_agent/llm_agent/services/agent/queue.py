from __future__ import annotations

from typing import Protocol
from uuid import UUID


class JobQueue(Protocol):
    async def enqueue(self, job_id: UUID) -> None: ...

    async def claim_next(self, worker_id: str) -> UUID | None: ...

    async def heartbeat(self, job_id: UUID, worker_id: str) -> None: ...
