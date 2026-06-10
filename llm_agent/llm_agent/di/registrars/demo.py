from __future__ import annotations

import svcs

from agent_run_worker.demo.agent_worker import DemoAgentWorker
from agent_run_worker.demo.config import DemoAgentSettings
from agent_run_worker.demo.mcp_client import DemoMcpToolClient, FastMcpDemoToolClient
from agent_run_worker.demo.model_client import DemoModelClient, build_demo_model_client
from agent_run_worker.demo.skill_loader import DemoSkillLoader, PackageDemoSkillLoader
from llm_agent.di.registrars.base import Registrar
from llm_agent.services.demo.reservation_service import DemoReservationService


class DemoAgentRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        registry.register_value(DemoAgentSettings, DemoAgentSettings())
        registry.register_factory(DemoSkillLoader, self.get_skill_loader)
        registry.register_factory(DemoMcpToolClient, self.get_mcp_client)
        registry.register_factory(DemoModelClient, self.get_model_client)
        registry.register_factory(DemoAgentWorker, self.get_agent_worker)
        registry.register_factory(DemoReservationService, self.get_reservation_service)

    @staticmethod
    def get_skill_loader() -> DemoSkillLoader:
        return PackageDemoSkillLoader()

    @staticmethod
    def get_mcp_client(svcs_container: svcs.Container) -> DemoMcpToolClient:
        return FastMcpDemoToolClient(settings=svcs_container.get(DemoAgentSettings))

    @staticmethod
    def get_model_client(svcs_container: svcs.Container) -> DemoModelClient | None:
        return build_demo_model_client(settings=svcs_container.get(DemoAgentSettings))

    @staticmethod
    def get_agent_worker(svcs_container: svcs.Container) -> DemoAgentWorker:
        return DemoAgentWorker(
            settings=svcs_container.get(DemoAgentSettings),
            skill_loader=svcs_container.get(DemoSkillLoader),
            mcp_client=svcs_container.get(DemoMcpToolClient),
            model_client=svcs_container.get(DemoModelClient),
        )

    @staticmethod
    def get_reservation_service(svcs_container: svcs.Container) -> DemoReservationService:
        return DemoReservationService(agent_worker=svcs_container.get(DemoAgentWorker))
