import asyncio

from llm_agent.services.agent.queue import JobSignalQueue


class InMemoryJobSignalQueue(JobSignalQueue):
    """
    Signals to wake up the worker.

    Either receiving an event from the orchestrator (rest api), or a default timeout.

        | Situation              | Result                       |
        | ---------------------- | ---------------------------- |
        | Job enqueued           | immediate wakeup             |
        | Worker crash elsewhere | timeout triggers recovery    |
        | Missed notify          | timeout saves you            |
        | No jobs                | periodic lightweight polling |
        | Shutdown               | loop exits cleanly           |
    """

    def __init__(self):
        self._event = asyncio.Event()
        self._default_timeout = 5

    async def wait(self, timeout: None | float = None) -> None:
        """
        Wait for notification signal or the timeout.

        :param timeout:
        :return:
        """
        timeout = timeout or self._default_timeout

        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        finally:
            self._event.clear()

    async def notify(self) -> None:
        """
        Notify the workers there is a new job.
        """
        self._event.set()
