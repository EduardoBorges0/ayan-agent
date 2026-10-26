import pytest
from fastapi.testclient import TestClient

from app_router import app

client = TestClient(app)


@pytest.mark.smoke
def test_app_is_up():
    response = client.get("/api/v1/health")

    assert response.status_code == 200
