import uuid

from pydantic import BaseModel


class CreatedJobDto(BaseModel):
    id: uuid.UUID
