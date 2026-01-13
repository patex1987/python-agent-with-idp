from llm_agent.domain.agent.runs.transition_rules import DEFAULT_TRANSITION_RULES
from contracts.domain.runs.status_code import RunStatusCode
from contracts.domain.runs.status import RunStatus


class RunTransitionPolicy:
    def __init__(self, transition_rules: dict[RunStatusCode, tuple[RunStatusCode]] | None = None):
        """
        :param transition_rules:
        """
        if not transition_rules:
            transition_rules = DEFAULT_TRANSITION_RULES
        self.transition_rules = transition_rules

    def validate(self, run_status: RunStatus, new_status: RunStatusCode) -> None:
        """
        Validate if the transition to the desired run status is allowed and valid.

        :param run_status:
        :param new_status:
        :return:
        """
        if run_status.status not in self.transition_rules:
            raise ValueError(f"Unknown run status: {run_status.status}")
        if new_status not in self.transition_rules[run_status.status]:
            raise ValueError(f"Invalid transition: {run_status.status} -> {new_status}")
