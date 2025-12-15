import structlog
from pydantic import BaseModel

from llm_agent.domain.grid.coordinate import Coordinate


class UnitGoalDto(BaseModel):
    coordinate: Coordinate
    throttle: float


if __name__ == "__main__":
    logger = structlog.get_logger(__name__)
    # logger.info(UnitGoalDto(coordinate=Coordinate(x=0, y=0), throttle=0.5).model_dump_json())
    unit = UnitGoalDto.model_validate_json('{"coordinate": {"x": 0, "y": 0}, "throttle": 0.5}')
    logger.info(unit)
    x = unit.model_construct()
    logger.info(unit.model_construct())
