import asyncio
from collections import deque
from uuid import UUID

from llm_agent.domain.agent.jobs.event import JobEvent, get_current_utc_timestamp
from llm_agent.services.agent.event_log import JobEventLog


class InMemoryJobEventLog(JobEventLog):
    """
    TODO: Think about optimizing the lock usage
        Option 2: Keep async but optimize
            Keep asyncio.Lock but minimize work inside the lock
            Do expensive operations (like timestamp generation) outside the lock when possible
            Use per-job locks instead of a global lock (more complex)
    """

    def __init__(self):
        self._internal_job_events: dict[UUID, deque[JobEvent]] = {}
        self._next_sequence_nr: dict[UUID, int] = {}
        self._lock = asyncio.Lock()

    async def init_job_stream(self, job_id: UUID) -> None:
        async with self._lock:
            if job_id in self._internal_job_events:
                return
            self._internal_job_events[job_id] = deque()
            self._next_sequence_nr[job_id] = 1

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

        TODO: use a custom error for non-existing jobs
        """
        async with self._lock:
            if job_id not in self._internal_job_events:
                raise ValueError(f"Job {job_id} not found")

            sequence_nr = self._next_sequence_nr[job_id]
            self._next_sequence_nr[job_id] += 1
            job_event = JobEvent(
                job_id=job_id,
                sequence_nr=sequence_nr,
                event_type=event_type,
                payload=payload,
                timestamp_utc=get_current_utc_timestamp(),
            )
            self._internal_job_events[job_id].append(job_event)
            return job_event

    async def list(self, job_id: UUID, *, after_sequence: int | None = None) -> list[JobEvent]:
        """
        List all events from the given job after the provided sequence_nr.

        :param job_id:
        :param after_sequence:
        :return:
        """
        async with self._lock:
            if job_id not in self._internal_job_events:
                raise ValueError(f"Job {job_id} not found")

            if after_sequence is None:
                return list(self._internal_job_events[job_id])
            else:
                return [
                    job_event
                    for job_event in self._internal_job_events[job_id]
                    if job_event.sequence_nr > after_sequence
                ]
