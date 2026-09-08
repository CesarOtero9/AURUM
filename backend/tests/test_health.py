from fastapi.testclient import TestClient

from aurum.api.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "aurum-api",
        "version": "0.1.0",
    }
