from __future__ import annotations

from enum import Enum


class RunStatusCode(Enum):
    """
    CREATED
        Run record exists
        Not yet visible to workers
        Used for validation / idempotency
        Very short-lived
    ENQUEUED
        Run is eligible for workers
        No worker owns it yet
        Safe to retry enqueue
    RUNNING
        Worker has claimed run
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
        This does not mean execution has stopped.
        It means execution is no longer allowed to make progress.
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
    """

    CREATED = 1
    ENQUEUED = 2
    RUNNING = 3
    SUCCEEDED = 4
    FAILED = 5
    CANCELLED = 6
    TIMED_OUT = 7
    RETRYING = 8


TERMINAL_RUN_STATUSES = {RunStatusCode.SUCCEEDED, RunStatusCode.FAILED, RunStatusCode.CANCELLED}

