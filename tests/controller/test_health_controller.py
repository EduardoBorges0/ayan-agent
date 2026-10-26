from unittest.mock import patch

from fastapi.testclient import TestClient

from app_router import app

client = TestClient(app)


def test_health_returns_200_with_status_ok():
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_every_response_carries_a_request_id_header():
    response = client.get("/api/v1/health")

    assert response.headers.get("X-Request-ID")


@patch("controller.health_controller.HealthService")
def test_unexpected_error_returns_generic_500_without_internal_details(mock_service):
    mock_service.get_status.side_effect = RuntimeError("connection string secreta")

    response = client.get("/api/v1/health")

    assert response.status_code == 500
    assert response.json() == {"detail": "Erro interno do servidor."}
    assert "secreta" not in response.text
    assert response.headers.get("X-Request-ID")
