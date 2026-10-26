from service.health_service import HealthService


def test_get_status_returns_success_with_status_ok():
    result = HealthService.get_status()

    assert result["success"] is True
    assert result["data"].status == "ok"
