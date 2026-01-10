from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class RunEvent:
    """
    Sending live updates about the run status (websocket, sse).
    """

    run_id: UUID
    sequence_nr: int
    event_type: str
    payload: dict[str, Any]
    timestamp_utc: datetime.datetime


def get_current_utc_timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

