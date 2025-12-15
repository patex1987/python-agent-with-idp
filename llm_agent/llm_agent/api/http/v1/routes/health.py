from fastapi import APIRouter

health_router = APIRouter()


@health_router.get("/dummy-health")
async def dummy_health():
    return {"status": "ok"}
