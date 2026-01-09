import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class JobEventDto(BaseModel):
    """
    Job event response.

    Represents a single event in the job's event log.
    """

    sequence_nr: int
    event_type: str
    payload: dict[str, Any]
    timestamp_utc: datetime.datetime

