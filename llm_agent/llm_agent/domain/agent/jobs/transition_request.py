from dataclasses import dataclass, field
from typing import Any

class _UnsetField:
    __slots__ = ()
    def __repr__(self) -> str:
        return "UNSET"

UNSET_FIELD = _UnsetField()



@dataclass(frozen=True)
class TransitionRequestParams:
    """
    Request to transition a job to a new status.
    """

    result: dict[str, Any] | None | _UnsetField = field(default=UNSET_FIELD)
    error: str | None | _UnsetField = field(default=UNSET_FIELD)
    worker_id: str | None | _UnsetField = field(default=UNSET_FIELD)
    retry_count: int | None | _UnsetField = field(default=UNSET_FIELD)
    expiration_unix_ts: int | float | None | _UnsetField = field(default=UNSET_FIELD)


def get_value_or_fallback(transition_request_value, job_status_value):
    """Get transition request value if not MISSING, otherwise job status."""
    return transition_request_value if transition_request_value is not UNSET_FIELD else job_status_value
