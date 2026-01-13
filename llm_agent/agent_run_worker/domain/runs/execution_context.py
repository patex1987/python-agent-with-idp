import asyncio
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contracts.domain.runs.event import RunEvent
    from contracts.services.event_log import RunEventLog


class RunExecutionContext:
    """
    Execution context for a run that provides cancellation signaling and event emission.

    This context provides:
    - Cancellation signaling: coordinate graceful cancellation of the run executor
      (which checks for cancellation at checkpoints)
    - Event emission: emit events during run execution with run_id automatically included
    - Run identification: access to the run_id for the current execution

    The context exists to provide controlled access to run execution capabilities,
    ensuring the executor can only emit events and check cancellation, not mutate
    run state directly. This abstraction removes the executor's direct access to
    RunProcessingStore.

    TODO: can be extended later with fence tokens.
    """

    def __init__(self, run_id: uuid.UUID, event_log: "RunEventLog"):
        """
        Initialize execution context for a run.

        :param run_id: The ID of the run being executed
        :param event_log: Event log for emitting events during execution
        """
        self.run_id = run_id
        self.cancellation_event = asyncio.Event()
        self._event_log = event_log

    def cancel(self):
        """
        Intention signal that the run should be cancelled.

        This sets the cancellation event, which will be detected by the run executor
        at the next checkpoint.
        """
        self.cancellation_event.set()

    def is_cancelled(self) -> bool:
        """
        Check if cancellation has been requested.

        Should be checked at checkpoints (between steps/operations).

        :return: True if cancellation has been requested, False otherwise
        """
        return self.cancellation_event.is_set()

    async def emit_event(self, *, event_type: str, payload: dict[str, str]) -> "RunEvent":
        """
        Emit an event for this run.

        The run_id is automatically included, so executors don't need to pass it.

        :param event_type: Type/name of the event
        :param payload: Event payload data
        :return: The created RunEvent
        """
        return await self._event_log.append(
            run_id=self.run_id,
            event_type=event_type,
            payload=payload,
        )
