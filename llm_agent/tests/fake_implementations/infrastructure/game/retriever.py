from llm_agent.domain.game.game_state import GameState
from llm_agent.domain.game.retriever import GameStateRetriever
from llm_agent.domain.game.unit import Unit
from llm_agent.domain.grid.coordinate import Coordinate


class RandomGameStateRetriever(GameStateRetriever):
    def get_current_state(self) -> GameState:
        state = GameState(
            player_units=[Unit(coordinate=Coordinate(x=0, y=0), speed=0, mass=10, friction=0.01)],
            enemy_units=[Unit(coordinate=Coordinate(x=0, y=5000), speed=0, mass=50, friction=0.8)],
        )
        return state
