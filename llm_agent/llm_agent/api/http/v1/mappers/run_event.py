from llm_agent.api.http.v1.dto.run_event import RunEventDto
from contracts.domain.runs.event import RunEvent


class RunEventV1Mapper:
    """REST RunEventDto <-> Domain RunEvent"""

    @classmethod
    def to_dto(cls, run_event: RunEvent) -> RunEventDto:
        return RunEventDto(
            sequence_nr=run_event.sequence_nr,
            event_type=run_event.event_type,
            payload=run_event.payload,
            timestamp_utc=run_event.timestamp_utc,
        )

