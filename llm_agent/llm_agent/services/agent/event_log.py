from typing import Protocol
from uuid import UUID

from llm_agent.domain.agent.jobs.event import JobEvent


class JobEventLog(Protocol):
    """
    Append only event log for agent jobs.
    """

    async def init_job_stream(self, job_id: UUID) -> None:
        """
        Create an empty event stream for a job.
        :param job_id:
        :return:
        """
        ...

    async def append(self, job_id: UUID, *, event_type: str, payload: dict[str, str]) -> JobEvent:
        """
        Append a new event to the job's stream

        It must ensure:
        - atomic sequence nr
        - assign a timestamp
        - guarantee ordering

        :param job_id:
        :param event_type:
        :param payload:
        :return:
        """
        ...

    async def list(self, job_id: UUID, *, after_sequence: int | None = None) -> list[JobEvent]:
        """
        List all events from the given job after the provided sequence_nr.

        :param job_id:
        :param after_sequence:
        :return:
        """
        ...
