from llm_agent.domain.agent.jobs.transition_rules import DEFAULT_TRANSITION_RULES
from llm_agent.domain.agent.jobs.status_code import JobStatusCode
from llm_agent.domain.agent.jobs.status import JobStatus


class JobTransitionPolicy:
    def __init__(self, transition_rules: dict[JobStatusCode, tuple[JobStatusCode]] | None = None):
        """
        TODO: missing DI
        :param transition_rules:
        """
        if not transition_rules:
            transition_rules = DEFAULT_TRANSITION_RULES
        self.transition_rules = transition_rules

    def validate(self, job_status: JobStatus, new_status: JobStatusCode) -> None:
        """
        Validate if the transition to the desired job status is allowed and valid.

        :param job_status:
        :param new_status:
        :return:
        """
        if job_status.status not in self.transition_rules:
            raise ValueError(f"Unknown job status: {job_status.status}")
        if new_status not in self.transition_rules[job_status.status]:
            raise ValueError(f"Invalid transition: {job_status.status} -> {new_status}")
