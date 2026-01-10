import datetime
from typing import Any

from pydantic import BaseModel


class RunEventDto(BaseModel):
    """
    Run event response.

    Represents a single event in the run's event log.
    """

    sequence_nr: int
    event_type: str
    payload: dict[str, Any]
    timestamp_utc: datetime.datetime

