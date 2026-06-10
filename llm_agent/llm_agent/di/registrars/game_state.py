import svcs

from llm_agent.di.registrars.base import Registrar
from llm_agent.domain.game.retriever import GameStateRetriever
from llm_agent.infrastructure.game.retriever.static import StaticGameStateRetriever


class GameStateRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        registry.register_value(GameStateRetriever, StaticGameStateRetriever())
