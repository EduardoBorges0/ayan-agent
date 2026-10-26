from data.model.health_model import HealthResponse


class HealthService:
    @staticmethod
    def get_status() -> dict:
        return {"success": True, "data": HealthResponse(status="ok")}
