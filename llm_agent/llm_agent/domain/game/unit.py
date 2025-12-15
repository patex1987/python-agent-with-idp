from dataclasses import dataclass

from llm_agent.domain.grid.coordinate import Coordinate


@dataclass
class Unit:
    coordinate: Coordinate
    speed: float
    mass: float
    friction: float
