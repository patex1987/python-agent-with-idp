from typing import Protocol


class Consumer(Protocol):
    async def consume_and_execute_loop(self):
        """
        The main entrypoint / workhorse on the consumer side.
        :return:
        """
        ...

    async def shutdown_execution(self): ...
