from pydantic import BaseModel

from llm_agent.api.http.v1.dto.unit import UnitDto


class GameStateDto(BaseModel):
    player_units: list[UnitDto]
    enemy_units: list[UnitDto]
