from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from llm_agent.domain.agent.jobs.status import JobStatus


@dataclass(frozen=True)
class ClaimedJob:
    """
    Api agent job execution status.
    """

    id: UUID
    claim_type: enqueued | running_lost_claim
    job_status: JobStatus
