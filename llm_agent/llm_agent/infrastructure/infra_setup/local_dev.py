from llm_agent.domain.infrastructure_setup import InfrastructureSetup


class LocalDevInfrastructureSetup(InfrastructureSetup):
    """
    No-op infrastructure setup for local development.

    This implementation does not perform any infrastructure setup or teardown,
    making it suitable for local development environments where infrastructure
    resources are managed externally or not required.
    """

    async def setup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
