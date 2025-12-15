from dataclasses import dataclass

from llm_agent.domain.grid.coordinate import Coordinate


@dataclass
class UnitGoal:
    coordinate: Coordinate
    throttle: float
