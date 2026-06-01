from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_parent


def test_parent_registration_succeeds(client: TestClient):
    resp = client.post("/api/v1/auth/register", json={
        "email": "new@test.com",
        "password": "TestPass123",
        "display_name": "New Parent",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_duplicate_email_rejected(client: TestClient):
    client.post("/api/v1/auth/register", json={
        "email": "dup@test.com", "password": "TestPass123", "display_name": "A"
    })
    resp = client.post("/api/v1/auth/register", json={
        "email": "dup@test.com", "password": "TestPass123", "display_name": "B"
    })
    assert resp.status_code == 409


def test_email_is_case_insensitive(client: TestClient):
    client.post("/api/v1/auth/register", json={
        "email": "CASE@test.com", "password": "TestPass123", "display_name": "A"
    })
    resp = client.post("/api/v1/auth/register", json={
        "email": "case@test.com", "password": "TestPass123", "display_name": "B"
    })
    assert resp.status_code == 409


def test_parent_login_succeeds(client: TestClient):
    register_parent(client)
    resp = client.post("/api/v1/auth/login", json={
        "email": "parent@test.com", "password": "TestPass123"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_wrong_password_rejected(client: TestClient):
    register_parent(client)
    resp = client.post("/api/v1/auth/login", json={
        "email": "parent@test.com", "password": "WrongPassword"
    })
    assert resp.status_code == 401


def test_unknown_email_rejected(client: TestClient):
    resp = client.post("/api/v1/auth/login", json={
        "email": "nobody@test.com", "password": "TestPass123"
    })
    assert resp.status_code == 401


def test_refresh_token_succeeds(client: TestClient):
    tokens = register_parent(client)
    resp = client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["refresh_token"] != tokens["refresh_token"]  # rotated


def test_used_refresh_token_rejected(client: TestClient):
    tokens = register_parent(client)
    # Use the token once
    new_tokens = client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    }).json()
    # Use the old token again — must be rejected
    resp = client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert resp.status_code == 401
    # But the new token still works
    resp2 = client.post("/api/v1/auth/refresh", json={
        "refresh_token": new_tokens["refresh_token"]
    })
    assert resp2.status_code == 200


def test_logout_revokes_refresh_token(client: TestClient):
    tokens = register_parent(client)
    client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_unauthenticated_protected_route_returns_401(client: TestClient):
    resp = client.get("/api/v1/me")
    assert resp.status_code == 401


def test_wrong_role_returns_403(client: TestClient):
    # Register parent, use their token to hit a student-only route
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/students/first-login",
        json={"new_password": "NewPass123"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_me_returns_role(client: TestClient):
    tokens = register_parent(client)
    resp = client.get("/api/v1/me", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["role"] == "parent"


def test_short_password_rejected(client: TestClient):
    resp = client.post("/api/v1/auth/register", json={
        "email": "short@test.com", "password": "abc", "display_name": "A"
    })
    assert resp.status_code == 422


def test_invalid_email_rejected(client: TestClient):
    resp = client.post("/api/v1/auth/register", json={
        "email": "not-an-email", "password": "TestPass123", "display_name": "A"
    })
    assert resp.status_code == 422
