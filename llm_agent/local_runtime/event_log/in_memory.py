import asyncio
from collections import deque
from uuid import UUID

from llm_agent.domain.agent.runs.event import RunEvent, get_current_utc_timestamp
from llm_agent.services.agent.event_log import RunEventLog


class InMemoryRunEventLog(RunEventLog):
    """
    TODO: Think about optimizing the lock usage
        Option 2: Keep async but optimize
            Keep asyncio.Lock but minimize work inside the lock
            Do expensive operations (like timestamp generation) outside the lock when possible
            Use per-run locks instead of a global lock (more complex)
    """

    def __init__(self):
        self._internal_run_events: dict[UUID, deque[RunEvent]] = {}
        self._next_sequence_nr: dict[UUID, int] = {}
        self._lock = asyncio.Lock()

    async def init_run_stream(self, run_id: UUID) -> None:
        async with self._lock:
            if run_id in self._internal_run_events:
                return
            self._internal_run_events[run_id] = deque()
            self._next_sequence_nr[run_id] = 1

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

        TODO: use a custom error for non-existing runs
        """
        async with self._lock:
            if run_id not in self._internal_run_events:
                raise ValueError(f"Run {run_id} not found")

            sequence_nr = self._next_sequence_nr[run_id]
            self._next_sequence_nr[run_id] += 1
            run_event = RunEvent(
                run_id=run_id,
                sequence_nr=sequence_nr,
                event_type=event_type,
                payload=payload,
                timestamp_utc=get_current_utc_timestamp(),
            )
            self._internal_run_events[run_id].append(run_event)
            return run_event

    async def list(self, run_id: UUID, *, after_sequence: int | None = None) -> list[RunEvent]:
        """
        List all events from the given run after the provided sequence_nr.

        :param run_id:
        :param after_sequence:
        :return:
        """
        async with self._lock:
            if run_id not in self._internal_run_events:
                raise ValueError(f"Run {run_id} not found")

            if after_sequence is None:
                return list(self._internal_run_events[run_id])
            else:
                return [
                    run_event
                    for run_event in self._internal_run_events[run_id]
                    if run_event.sequence_nr > after_sequence
                ]
