import asyncio
import uuid


class JobExecutionContext:
    """
    Execution context for a job that provides cancellation signaling.

    This context is used to coordinate graceful cancellation of the job
    executor (which checks for cancellation at checkpoints).
    It exists to stop work, not to decide the state.

    TODO: can be extended later with fence tokens.
    """

    def __init__(self, job_id: uuid.UUID):
        self.job_id = job_id
        self.cancellation_event = asyncio.Event()

    def cancel(self):
        """
        Intention signal that the job should be cancelled.

        This sets the cancellation event, which will be detected by the job executor
        at the next checkpoint.
        """
        self.cancellation_event.set()

    def is_cancelled(self):
        """
        Check if cancellation has been requested.

        :return: True if cancellation has been requested, False otherwise
        """
        return self.cancellation_event.is_set()
