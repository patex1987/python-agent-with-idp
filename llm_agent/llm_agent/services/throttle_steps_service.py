from llm_agent.domain.game.game_state import GameState
from llm_agent.domain.grid.goal import UnitGoal
from llm_agent.domain.navigation.path_finder import PathFinderStrategy


class ThrottleStepsService:
    def __init__(self, path_finder: PathFinderStrategy):
        self.path_finder = path_finder

    def calculate_throttle_steps(self, game_state: GameState) -> list[UnitGoal]:
        return self.path_finder.find_path(game_state, game_state.player_units[0], game_state.enemy_units[0])
