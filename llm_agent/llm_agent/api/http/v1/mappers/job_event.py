from llm_agent.api.http.v1.dto.job_event import JobEventDto
from llm_agent.domain.agent.jobs.event import JobEvent


class JobEventV1Mapper:
    """REST JobEventDto <-> Domain JobEvent"""

    @classmethod
    def to_dto(cls, job_event: JobEvent) -> JobEventDto:
        return JobEventDto(
            sequence_nr=job_event.sequence_nr,
            event_type=job_event.event_type,
            payload=job_event.payload,
            timestamp_utc=job_event.timestamp_utc,
        )

