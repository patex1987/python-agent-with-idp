from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class JobEvent:
    """
    Sending live updates about the job status (websocket, sse).
    """

    job_id: UUID
    event_type: str
    payload: dict[str, Any]
