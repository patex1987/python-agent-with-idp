from typing import Protocol

from llm_agent.domain.game.game_state import GameState
from llm_agent.domain.game.unit import Unit
from llm_agent.domain.grid.goal import UnitGoal


class PathFinderStrategy(Protocol):
    def find_path(self, game_state: GameState, main_unit: Unit, target_unit: Unit) -> list[UnitGoal]: ...
