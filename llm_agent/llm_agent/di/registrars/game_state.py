import svcs

from tests.fake_implementations.infrastructure.game.retriever import RandomGameStateRetriever
from llm_agent.di.registrars.base import Registrar
from llm_agent.domain.game.retriever import GameStateRetriever


class GameStateRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        registry.register_value(GameStateRetriever, RandomGameStateRetriever())
