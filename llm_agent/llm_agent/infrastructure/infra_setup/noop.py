from llm_agent.domain.infrastructure_setup import InfrastructureSetup


class NoopInfrastructureSetup(InfrastructureSetup):
    async def setup(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None
