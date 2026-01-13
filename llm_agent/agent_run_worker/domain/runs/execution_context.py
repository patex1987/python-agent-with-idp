import asyncio
import uuid


class RunExecutionContext:
    """
    Execution context for a run that provides cancellation signaling.

    This context is used to coordinate graceful cancellation of the run
    executor (which checks for cancellation at checkpoints).
    It exists to stop work, not to decide the state.

    TODO: can be extended later with fence tokens.
    """

    def __init__(self, run_id: uuid.UUID):
        self.run_id = run_id
        self.cancellation_event = asyncio.Event()

    def cancel(self):
        """
        Intention signal that the run should be cancelled.

        This sets the cancellation event, which will be detected by the run executor
        at the next checkpoint.
        """
        self.cancellation_event.set()

    def is_cancelled(self):
        """
        Check if cancellation has been requested.

        :return: True if cancellation has been requested, False otherwise
        """
        return self.cancellation_event.is_set()

