from __future__ import annotations

from typing import Protocol, AsyncIterator
from uuid import UUID

from llm_agent.domain.agent.jobs.event import JobEvent


class JobNotifier(Protocol):
    async def publish(self, evt: JobEvent) -> None: ...

    async def subscribe(self, job_id: UUID) -> AsyncIterator[JobEvent]: ...
