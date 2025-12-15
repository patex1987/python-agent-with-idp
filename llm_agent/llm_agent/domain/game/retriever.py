from typing import Protocol

from llm_agent.domain.game.game_state import GameState


class GameStateRetriever(Protocol):
    def get_current_state(self) -> GameState: ...
