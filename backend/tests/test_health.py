from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_ok_status():
    response = client.get("/api/health")
    body = response.json()
    assert body["status"] == "ok"


def test_health_returns_service_name():
    response = client.get("/api/health")
    body = response.json()
    assert body["service"] == "hsc-ai-backend"


def test_health_returns_version():
    response = client.get("/api/health")
    body = response.json()
    assert "version" in body
    assert isinstance(body["version"], str)
    assert len(body["version"]) > 0


def test_health_response_shape():
    response = client.get("/api/health")
    body = response.json()
    assert set(body.keys()) == {"status", "service", "version"}
