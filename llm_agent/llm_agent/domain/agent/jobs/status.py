from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from llm_agent.domain.agent.jobs.status_code import JobStatusCode


@dataclass(frozen=True)
class JobStatus:
    """
    Job status response.
    """

    id: UUID
    status: JobStatusCode
    result: dict[str, Any] | None
    error: str | None
    claimed_worker: str | None = None
    claim_expiration_unix_ts: float | None = None
    retry_count: int | None = 0
