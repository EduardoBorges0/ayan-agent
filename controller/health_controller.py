from fastapi import APIRouter

from data.model.health_model import HealthResponse
from service.health_service import HealthService

router = APIRouter()


@router.get("", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthService.get_status()["data"]
