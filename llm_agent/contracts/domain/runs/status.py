from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from contracts.domain.runs.status_code import RunStatusCode


@dataclass(frozen=True)
class RunStatus:
    """
    Run status response.
    """

    id: UUID
    status: RunStatusCode
    result: dict[str, Any] | None
    error: str | None
    claimed_worker: str | None = None
    claim_expiration_unix_ts: float | None = None
    retry_count: int | None = 0

    # intent-driven flags
    cancel_requested: bool = False
