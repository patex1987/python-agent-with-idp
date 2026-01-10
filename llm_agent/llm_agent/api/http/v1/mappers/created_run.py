from llm_agent.api.http.v1.dto.created_run import CreatedRunDto
from llm_agent.domain.agent.runs.status import RunStatus


class CreatedRunV1Mapper:
    """Rest CreatedRunDto <-> Domain RunStatus"""

    @classmethod
    def to_dto(cls, run_status: RunStatus) -> CreatedRunDto:
        return CreatedRunDto(id=run_status.id)

