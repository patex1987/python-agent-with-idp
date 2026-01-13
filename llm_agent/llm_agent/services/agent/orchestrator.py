from uuid import UUID

from contracts.domain.runs.event import RunEvent
from llm_agent.domain.agent.runs.request import RunRequest
from contracts.domain.runs.status import RunStatus
from contracts.services.queue import RunSignalQueue
from llm_agent.services.agent.store import RunIntakeStore


class BackendRunOrchestrationService:
    def __init__(
        self,
        run_store: RunIntakeStore,
        run_signal_queue: RunSignalQueue,
    ):
        self.run_store = run_store
        self.run_signal_queue = run_signal_queue

    async def create_run(self, prompt: str) -> RunStatus:
        """

        :param prompt:
        :return:
        """
        run_request = RunRequest(
            prompt=prompt,
            history=[],
            user_id="hardcoded_user_later_take_it_from_context",
        )
        created_run = await self.run_store.create_run(
            run_request=run_request,
        )
        await self.run_store.mark_enqueued(created_run.id)
        await self.run_signal_queue.notify()
        return created_run

    async def get_run(self, run_id: UUID) -> RunStatus:
        """
        Retrieve the run's status from the run store.

        :param run_id:
        :return: RunStatus
        :raises: RunNotFoundError
        """
        run_status = await self.run_store.get_status(run_id=run_id)
        return run_status

    async def cancel_run(self, run_id: UUID) -> bool:
        """
        Mark the run as canceled, notify the workers when the run state needs transition.

        :param run_id:
        :return:
        TODO: return proper domain objects instead of bool if needed
        """
        is_cancelled = await self.run_store.request_cancellation(run_id=run_id)
        if is_cancelled:
            await self.run_signal_queue.notify()

        return is_cancelled

    async def get_events(self, run_id: UUID, after_sequence: int | None = None) -> list[RunEvent]:
        """
        Retrieve events for a run from the run store's event log.

        :param run_id: The run ID
        :param after_sequence: Optional sequence number to filter events after
        :return: List of run events
        :raises: RunNotFoundError if the run is not found
        :raises: ValueError if event log is not available
        """
        return await self.run_store.get_events(run_id=run_id, after_sequence=after_sequence)
