import uuid

from pydantic import BaseModel


class CancelJobResponseDto(BaseModel):
    job_id: uuid.UUID
    status: str
    message: str
