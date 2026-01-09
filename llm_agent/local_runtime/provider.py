import uuid
from collections import deque
from dataclasses import dataclass

from llm_agent.domain.agent.jobs.event import JobEvent
from llm_agent.domain.agent.jobs.status import JobStatus
from local_runtime.job_signal_queue.queue import InMemoryJobSignalQueue


@dataclass
class InMemoryRuntime:
    """
    In-memory infrastructure building blocks that are shared between the job orchestrator and the workers

    Used for local development and service execution.
    Use the dockerized setup for a close-to-production like setup

    TODO: create a class for InMemoryJobEventLog ( a wrapper around internal event logs)
    """

    internal_job_storage: dict[uuid.UUID, JobStatus]
    internal_event_logs: dict[uuid.UUID, deque[JobEvent]]
    job_signal_queue: InMemoryJobSignalQueue


def create_default_in_memory_runtime() -> InMemoryRuntime:
    return InMemoryRuntime(
        internal_job_storage={},
        internal_event_logs={},
        job_signal_queue=InMemoryJobSignalQueue(),
    )
