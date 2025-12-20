from __future__ import annotations

from enum import Enum


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
