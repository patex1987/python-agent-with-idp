import svcs
from svcs import Container

from llm_agent.di.registrars.base import Registrar
from llm_agent.domain.genetic_path.configuration import GeneticConfiguration
from llm_agent.infrastructure.navigation.path_finders.genetic import GeneticPathFinderStrategy
from llm_agent.domain.navigation.path_finder import PathFinderStrategy
from llm_agent.services.throttle_steps_service import ThrottleStepsService


class ThrottleStepsServiceRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        registry.register_factory(PathFinderStrategy, factory=self.__class__.get_path_finder)
        registry.register_value(GeneticConfiguration, GeneticConfiguration())

        registry.register_factory(ThrottleStepsService, factory=self.__class__.get_throttle_step_service)

    @classmethod
    def get_path_finder(cls, svcs_container: Container) -> PathFinderStrategy:
        genetic_configuration = svcs_container.get(GeneticConfiguration)
        return GeneticPathFinderStrategy(genetic_configration=genetic_configuration)

    # def get_path_finder_2(self) -> PathFinderStrategy:
    #     return RandomDummyPathFinderStrategy()

    @classmethod
    def get_throttle_step_service(cls, svcs_container: Container) -> ThrottleStepsService:
        path_finder = svcs_container.get(PathFinderStrategy)
        return ThrottleStepsService(path_finder=path_finder)
