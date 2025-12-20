import uuid

from pydantic import BaseModel


class CreatedJobDto(BaseModel):
    job_id: uuid.UUID
