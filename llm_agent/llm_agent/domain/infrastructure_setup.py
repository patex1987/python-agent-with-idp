from typing import Protocol


class InfrastructureSetup(Protocol):
    """
    Protocol defining the interface for infrastructure setup and teardown.

    Implementations of this protocol are responsible for managing the lifecycle
    of infrastructure resources (e.g., database connection pools, external service
    connections) during application startup and shutdown.
    """

    async def setup(self) -> None:
        """
        Initialize infrastructure resources.

        This method is called during application startup (FastAPI lifespan)
        to set up infrastructure dependencies.
        """
        ...

    async def shutdown(self) -> None:
        """
        Clean up infrastructure resources.

        This method is called during application shutdown (FastAPI lifespan)
        to gracefully tear down infrastructure dependencies.
        """
        ...
