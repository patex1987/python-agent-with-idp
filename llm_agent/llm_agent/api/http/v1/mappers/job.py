from llm_agent.api.http.v1.dto.job import JobDto
from llm_agent.domain.agent.jobs.status import JobStatus


class JobV1Mapper:
    """REST JobDto <-> Domain JobStatus"""

    @classmethod
    def to_dto(cls, job_status: JobStatus) -> JobDto:
        return JobDto(
            id=job_status.id,
            status=job_status.status.name,
            result=job_status.result,
            error=job_status.error,
            cancel_requested=job_status.cancel_requested,
        )

