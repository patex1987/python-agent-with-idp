from llm_agent.api.http.v1.dto.created_job import CreatedJobDto
from llm_agent.domain.agent.jobs.status import JobStatus


class CreatedJobV1Mapper:
    """Rest CreatedJobDto <-> Domain JobStatus"""

    @classmethod
    def to_dto(cls, job_status: JobStatus) -> CreatedJobDto:
        return CreatedJobDto(job_id=job_status.id)
