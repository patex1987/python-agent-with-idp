from pydantic import BaseModel

from llm_agent.domain.grid.coordinate import Coordinate


class CoordinateDto(BaseModel):
    x: float
    y: float

    def to_coordinate(self) -> Coordinate:
        return Coordinate(x=self.x, y=self.y)


class UnitDto(BaseModel):
    coordinate: CoordinateDto
    speed: float
    mass: float
    friction: float
