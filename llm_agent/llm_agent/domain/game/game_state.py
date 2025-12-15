from dataclasses import dataclass

from llm_agent.domain.game.unit import Unit


@dataclass
class GameState:
    player_units: list[Unit]
    enemy_units: list[Unit]
