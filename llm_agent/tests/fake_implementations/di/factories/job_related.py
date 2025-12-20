"""
This is separated from the other parts of the DI, because we need to share
the job storage for internal single process job orchestration between the
rest api and the workers
"""

import uuid
from collections import deque

from llm_agent.domain.agent.jobs.status import JobStatus
from llm_agent.domain.agent.jobs.event import JobEvent


class InternalJobStorageProvider:
    _instance = None

    @classmethod
    def get_instance(cls) -> dict[uuid.UUID, JobStatus]:
        if cls._instance is None:
            cls._instance = {}
        return cls._instance


class InternalEventLogsProvider:
    _instance = None

    @classmethod
    def get_instance(cls) -> dict[uuid.UUID, deque[JobEvent]]:
        if cls._instance is None:
            cls._instance = {}
        return cls._instance


class InternalJobQueueProvider:
    _instance = None

    @classmethod
    def get_instance(cls) -> deque[uuid.UUID]:
        if cls._instance is None:
            cls._instance = deque()
        return cls._instance
