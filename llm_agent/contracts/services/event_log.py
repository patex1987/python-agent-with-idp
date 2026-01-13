from typing import Protocol
from uuid import UUID

from contracts.domain.runs.event import RunEvent


class RunEventLog(Protocol):
    """
    Append only event log for agent runs.
    """

    async def init_run_stream(self, run_id: UUID) -> None:
        """
        Create an empty event stream for a run.
        :param run_id:
        :return:
        """
        ...

    async def append(self, run_id: UUID, *, event_type: str, payload: dict[str, str]) -> RunEvent:
        """
        Append a new event to the run's stream

        It must ensure:
        - atomic sequence nr
        - assign a timestamp
        - guarantee ordering

        :param run_id:
        :param event_type:
        :param payload:
        :return:
        """
        ...

    async def list(self, run_id: UUID, *, after_sequence: int | None = None) -> list[RunEvent]:
        """
        List all events from the given run after the provided sequence_nr.

        :param run_id:
        :param after_sequence:
        :return:
        """
        ...
