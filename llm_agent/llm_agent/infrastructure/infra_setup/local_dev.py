import asyncio
import contextlib

from agent_job_worker.in_memory.consumer import Consumer
from llm_agent.domain.infrastructure_setup import InfrastructureSetup


class LocalDevInfrastructureSetup(InfrastructureSetup):
    """
    infrastructure setup for local development.

    Sets up things like:
    - background message job consumer - for processing the load coming fro
        the rest api
    """

    def __init__(self, consumer: Consumer):
        self.consumer = consumer
        self._task: asyncio.Task | None = None

    async def setup(self) -> None:
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self.consumer.consume_and_execute_loop())

    async def shutdown(self) -> None:
        await self.consumer.shutdown_execution()

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
