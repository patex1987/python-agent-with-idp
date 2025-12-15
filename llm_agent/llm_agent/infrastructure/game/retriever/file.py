import json

from llm_agent.domain.game.game_state import GameState
from llm_agent.domain.game.retriever import GameStateRetriever


class FileBasedGameStateRetriever(GameStateRetriever):
    def __init__(self, file_path: str):
        self.file_path = file_path

    def get_current_state(self) -> GameState:
        with open(self.file_path, "r") as file:
            content = file.read()
        raw_data = json.loads(content)

        game_state_domain = GameState(
            player_units=raw_data["player_units"],
            enemy_units=raw_data["enemy_units"],
        )
        return game_state_domain
