import uuid
from dataclasses import dataclass

from llm_agent.domain.agent.runs.status import RunStatus
from local_runtime.event_log.in_memory import InMemoryRunEventLog
from local_runtime.run_signal_queue.queue import InMemoryRunSignalQueue


@dataclass
class InMemoryRuntime:
    """
    In-memory infrastructure building blocks that are shared between the run orchestrator and the workers

    Used for local development and service execution.
    Use the dockerized setup for a close-to-production like setup

    TODO: create a class for InMemoryRunEventLog ( a wrapper around internal event logs)
    """

    internal_run_storage: dict[uuid.UUID, RunStatus]
    internal_event_logs: InMemoryRunEventLog
    run_signal_queue: InMemoryRunSignalQueue


def create_default_in_memory_runtime() -> InMemoryRuntime:
    return InMemoryRuntime(
        internal_run_storage={},
        internal_event_logs=InMemoryRunEventLog(),
        run_signal_queue=InMemoryRunSignalQueue(),
    )
