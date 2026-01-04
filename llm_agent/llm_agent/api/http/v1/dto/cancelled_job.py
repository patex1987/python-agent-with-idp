from pydantic import BaseModel


class CancelJobResponseDto(BaseModel):
    job_id: str
    status: str
    message: str
