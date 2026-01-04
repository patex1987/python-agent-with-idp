from dataclasses import dataclass, field, MISSING
from typing import Any


@dataclass(frozen=True)
class TransitionRequestParams:
    """
    Request to transition a job to a new status.
    """

    result: dict[str, Any] | None = (field(default=MISSING),)
    error: str | None = (field(default=MISSING),)
    worker_id: str | None = (field(default=MISSING),)
    retry_count: int | None = (field(default=MISSING),)
    expiration_unix_ts: int | float | None = (field(default=MISSING),)


def get_value_or_fallback(transition_request_value, job_status_value):
    """Get transition request value if not MISSING, otherwise job status."""
    return transition_request_value if transition_request_value is not MISSING else job_status_value
