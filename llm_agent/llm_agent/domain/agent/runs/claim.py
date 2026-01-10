from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from llm_agent.domain.agent.runs.status import RunStatus


@dataclass(frozen=True)
class ClaimedRun:
    """
    Api agent run execution status.
    """

    id: UUID
    claim_type: enqueued | running_lost_claim
    run_status: RunStatus

