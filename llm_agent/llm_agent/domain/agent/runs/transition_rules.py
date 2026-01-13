from __future__ import annotations

from contracts.domain.runs.status_code import RunStatusCode

DEFAULT_TRANSITION_RULES: dict[RunStatusCode, tuple[RunStatusCode]] = {
    RunStatusCode.CREATED: (RunStatusCode.ENQUEUED, RunStatusCode.CANCELLED),
    RunStatusCode.ENQUEUED: (RunStatusCode.RUNNING, RunStatusCode.CANCELLED),
    RunStatusCode.RUNNING: (
        RunStatusCode.SUCCEEDED,
        RunStatusCode.FAILED,
        RunStatusCode.CANCELLED,
        RunStatusCode.TIMED_OUT,
    ),
    RunStatusCode.SUCCEEDED: tuple(),
    RunStatusCode.FAILED: tuple(),
    RunStatusCode.CANCELLED: tuple(),
    RunStatusCode.TIMED_OUT: (RunStatusCode.RETRYING,),
    RunStatusCode.RETRYING: (RunStatusCode.ENQUEUED,),
}

