from llm_agent.api.http.v1.dto.run import RunDto
from contracts.domain.runs.status import RunStatus


class RunV1Mapper:
    """REST RunDto <-> Domain RunStatus"""

    @classmethod
    def to_dto(cls, run_status: RunStatus) -> RunDto:
        return RunDto(
            id=run_status.id,
            status=run_status.status.name,
            result=run_status.result,
            error=run_status.error,
            cancel_requested=run_status.cancel_requested,
        )
