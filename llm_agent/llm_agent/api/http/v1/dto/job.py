import uuid
from typing import Any

from pydantic import BaseModel


class JobDto(BaseModel):
    """
    Full job state response.

    Maps 1:1 to the domain JobStatus model, providing complete job information.
    """

    id: uuid.UUID
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    cancel_requested: bool = False

