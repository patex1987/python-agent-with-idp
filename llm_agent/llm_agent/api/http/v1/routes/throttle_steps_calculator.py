import logging

import fastapi
import svcs.fastapi
from fastapi import APIRouter, HTTPException

from llm_agent.api.http.v1.dto.game_state import GameStateDto
from llm_agent.api.http.v1.dto.unit_goal import UnitGoalDto
from llm_agent.api.http.v1.mappers.game_state import GameStateV1Mapper
from llm_agent.api.http.v1.mappers.unit_goal import UnitGoalMapperV1
from llm_agent.services.throttle_steps_service import ThrottleStepsService

throttle_router = APIRouter()

external_logger = logging.getLogger("external")


def get_throttle_step_service(services: svcs.fastapi.DepContainer) -> ThrottleStepsService:
    return services.get(ThrottleStepsService)


@throttle_router.post(
    "/calculate_throttle_steps",
    response_model=list[UnitGoalDto],
    summary="Compute throttle steps for first player/enemy unit",
)
async def throttle_steps(
    state: GameStateDto,
    request: fastapi.Request,
    step_service: ThrottleStepsService = fastapi.Depends(get_throttle_step_service),
):
    try:
        # Map DTO → domain GameState (if needed) or pass DTO directly

        # step_service = services.get(ThrottleStepsService)
        domain_state = GameStateV1Mapper.from_dto(state)
        goals = step_service.calculate_throttle_steps(domain_state)
        external_logger.info("router - coming from the outside world - python logger")
        # Assuming each UnitGoal has .unit_id and .path attributes
        return [UnitGoalMapperV1.to_dto(goal) for goal in goals]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
