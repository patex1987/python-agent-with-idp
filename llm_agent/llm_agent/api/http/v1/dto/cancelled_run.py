import uuid

from pydantic import BaseModel


class CancelRunResponseDto(BaseModel):
    run_id: uuid.UUID
    status: str
    message: str

