from __future__ import annotations

from agent_run_worker.demo.agent_worker import DemoAgentWorker
from agent_run_worker.demo.types import (
    DemoDependencyError,
    DemoReservationRequest,
    DemoReservationResult,
    DemoWorkflowTimeoutError,
)


class DemoReservationService:
    def __init__(self, agent_worker: DemoAgentWorker) -> None:
        self._agent_worker = agent_worker

    async def reserve_recommended_seat(self, request: DemoReservationRequest) -> DemoReservationResult:
        result = await self._agent_worker.run(request)

        if result.outcome == "dependency_failed":
            raise DemoDependencyError(result)

        if result.outcome == "max_steps_exceeded":
            raise DemoWorkflowTimeoutError(result)

        return result
