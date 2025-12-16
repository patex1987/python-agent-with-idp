from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class JobRequest:
    """
    Api agent job request to work processor.
    """

    prompt: str
    history: list[str]
    user_id: str


@dataclass(frozen=True)
class EnqueuedJob:
    """
    Use to check the status of the enqueued job.
    """

    id: UUID


class JobStatusCode(Enum):
    """
    CREATED
        Job record exists
        Not yet visible to workers
        Used for validation / idempotency
        Very short-lived
    ENQUEUED
        Job is eligible for workers
        No worker owns it yet
        Safe to retry enqueue
    RUNNING
        Worker has claimed job
        Lease / heartbeat active
        Progress events allowed
    SUCCEEDED
        Terminal
        Result available
        Immutable
    FAILED
        Terminal
        Error recorded
        Retry possible (new attempt)
    CANCELLED
        Terminal
        User/system decision
        No retry unless explicitly requeued
    TIMED_OUT
        Terminal (or transitional to RETRYING)
        Worker lost lease
        Treated differently from FAILED
    RETRYING

    Allowed state transitions:
    CREATED    → ENQUEUED
    ENQUEUED   → RUNNING
    RUNNING    → SUCCEEDED
    RUNNING    → FAILED
    RUNNING    → CANCELLED
    RUNNING    → TIMED_OUT
    TIMED_OUT  → RETRYING
    RETRYING   → ENQUEUED

    TODO: CANCELLATION NOT SUPPORTED YET
    """

    CREATED = 1
    ENQUEUED = 2
    RUNNING = 3
    SUCCEEDED = 4
    FAILED = 5
    CANCELLED = 6
    TIMED_OUT = 7
    RETRYING = 8


@dataclass(frozen=True)
class JobStatus:
    """
    Job status response.
    """

    id: UUID
    status: JobStatusCode
    progress: float | None
    result: dict[str, Any] | None
    error: str | None


@dataclass(frozen=True)
class JobEvent:
    """
    Sending live updates about the job status (websocket, sse).
    """

    job_id: UUID
    event_type: str
    payload: dict[str, Any]
