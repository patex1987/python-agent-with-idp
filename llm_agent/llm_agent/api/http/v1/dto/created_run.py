import uuid

from pydantic import BaseModel


class CreatedRunDto(BaseModel):
    id: uuid.UUID
