from __future__ import annotations

from llm_agent.domain.agent.jobs.status_code import JobStatusCode

DEFAULT_TRANSITION_RULES: dict[JobStatusCode, tuple[JobStatusCode]] = {
    JobStatusCode.CREATED: (JobStatusCode.ENQUEUED,),
    JobStatusCode.ENQUEUED: (JobStatusCode.RUNNING,),
    JobStatusCode.RUNNING: (
        JobStatusCode.SUCCEEDED,
        JobStatusCode.FAILED,
        JobStatusCode.CANCELLED,
        JobStatusCode.TIMED_OUT,
    ),
    JobStatusCode.SUCCEEDED: tuple(),
    JobStatusCode.FAILED: tuple(),
    JobStatusCode.CANCELLED: tuple(),
    JobStatusCode.TIMED_OUT: (JobStatusCode.RETRYING,),
    JobStatusCode.RETRYING: (JobStatusCode.ENQUEUED,),
}
