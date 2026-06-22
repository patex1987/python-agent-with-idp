from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contracts.domain.agent_executions.output import AgentExecutionOutput
from contracts.domain.agent_executions.request import AgentExecutionRequest
from contracts.domain.agent_executions.status_code import AgentExecutionStatusCode


@dataclass(frozen=True)
class AgentExecutionStatus:
    """
    Agent execution status response.
    """

    id: UUID
    status: AgentExecutionStatusCode
    request: AgentExecutionRequest
    result: AgentExecutionOutput | None
    error: str | None
    claimed_worker: str | None = None
    claim_expiration_unix_ts: float | None = None
    retry_count: int | None = 0

    # intent-driven flags
    cancel_requested: bool = False
