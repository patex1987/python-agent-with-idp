from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EnqueuedJob:
    """
    Use to check the status of the enqueued job.
    """

    id: UUID
