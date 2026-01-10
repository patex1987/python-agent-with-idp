import uuid
from typing import Any

from pydantic import BaseModel


class RunDto(BaseModel):
    """
    Full run state response.

    Maps 1:1 to the domain RunStatus model, providing complete run information.
    """

    id: uuid.UUID
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    cancel_requested: bool = False

