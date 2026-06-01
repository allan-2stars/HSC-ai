from fastapi.testclient import TestClient

from app.main import app

# Health tests use their own client (no DB override needed — health checks a real DB)
_client = TestClient(app, raise_server_exceptions=True)


def test_health_returns_200():
    resp = _client.get("/api/health")
    assert resp.status_code == 200


def test_health_includes_database_status():
    resp = _client.get("/api/health")
    body = resp.json()
    assert "database" in body
    assert body["database"] in ("ok", "error")


def test_health_includes_redis_status():
    resp = _client.get("/api/health")
    body = resp.json()
    assert "redis" in body
    assert body["redis"] in ("ok", "error")


def test_health_returns_service_name():
    resp = _client.get("/api/health")
    assert resp.json()["service"] == "hsc-ai-backend"


def test_health_returns_version():
    resp = _client.get("/api/health")
    body = resp.json()
    assert "version" in body
    assert isinstance(body["version"], str)


def test_health_response_shape():
    resp = _client.get("/api/health")
    body = resp.json()
    assert set(body.keys()) == {"status", "service", "version", "database", "redis"}


def test_health_database_ok_when_docker_up():
    """When the Docker stack is running, the database check must return ok."""
    resp = _client.get("/api/health")
    assert resp.json()["database"] == "ok"


def test_health_redis_ok_when_docker_up():
    """When the Docker stack is running, the Redis check must return ok."""
    resp = _client.get("/api/health")
    assert resp.json()["redis"] == "ok"
