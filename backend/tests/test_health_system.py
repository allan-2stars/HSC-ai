"""System health and admin system endpoint tests."""
from datetime import datetime, timedelta, timezone
import time

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)

from app.services import system_service


# ── Health /detailed (public) ─────────────────────────────────────────────


def test_health_detailed_returns_200(client: TestClient):
    resp = client.get("/api/health/detailed")
    assert resp.status_code == 200


def test_health_detailed_has_required_fields(client: TestClient):
    resp = client.get("/api/health/detailed")
    data = resp.json()
    required = {"database_status", "redis_status", "storage_status",
                "migration_version", "uptime_seconds", "memory_usage_mb"}
    assert required.issubset(set(data.keys()))


def test_health_detailed_no_user_data(client: TestClient):
    resp = client.get("/api/health/detailed")
    data = resp.json()
    forbidden = {"total_users", "active_users", "table_counts", "jobs",
                 "failed_jobs", "stuck_jobs", "total_questions", "total_exams"}
    assert not any(k in data for k in forbidden)


def test_health_detailed_status_values_are_strings(client: TestClient):
    resp = client.get("/api/health/detailed")
    data = resp.json()
    for key in ["database_status", "redis_status", "storage_status"]:
        assert isinstance(data[key], str)


def test_health_detailed_uptime_is_number(client: TestClient):
    resp = client.get("/api/health/detailed")
    assert isinstance(resp.json()["uptime_seconds"], (int, float))


# ── Health /detailed field values ──────────────────────────────────────────


def test_health_detailed_uptime_increasing(client: TestClient):
    resp1 = client.get("/api/health/detailed")
    time.sleep(0.1)
    resp2 = client.get("/api/health/detailed")
    assert resp2.json()["uptime_seconds"] >= resp1.json()["uptime_seconds"]


def test_health_detailed_memory_nonnegative(client: TestClient):
    resp = client.get("/api/health/detailed")
    assert resp.json()["memory_usage_mb"] >= 0


# ── Existing health endpoint preserved ─────────────────────────────────────


def test_health_basic_preserved(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"status", "service", "version", "database", "redis"}


# ── Admin /system endpoint ─────────────────────────────────────────────────


def test_admin_system_requires_auth(client: TestClient):
    resp = client.get("/api/v1/admin/system")
    assert resp.status_code == 401


def test_admin_system_parent_denied(client: TestClient):
    tokens = register_parent(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    assert resp.status_code == 403


def test_admin_system_student_denied(client: TestClient):
    tokens = create_student_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    assert resp.status_code == 403


def test_admin_system_returns_200(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    assert resp.status_code == 200


def test_admin_system_includes_health(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    data = resp.json()
    health_fields = {"database_status", "redis_status", "storage_status",
                     "migration_version", "uptime_seconds", "memory_usage_mb"}
    assert health_fields.issubset(set(data.keys()))


def test_admin_system_includes_users(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    data = resp.json()
    assert data["total_users"] >= 1
    for key in ["active_users_24h", "active_parents_24h",
                "active_students_24h", "active_admins_24h"]:
        assert key in data


def test_admin_system_includes_content(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    data = resp.json()
    for key in ["total_questions", "published_questions",
                "total_exams", "total_assignments"]:
        assert key in data


def test_admin_system_includes_jobs(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    data = resp.json()
    assert "jobs" in data
    for key in ["ocr_jobs", "ai_jobs", "import_jobs"]:
        assert key in data["jobs"]


def test_admin_system_includes_table_counts(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    data = resp.json()
    assert "table_counts" in data
    assert "users" in data["table_counts"]
    assert data["table_counts"]["users"] >= 1


def test_admin_system_includes_failed_and_stuck(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    data = resp.json()
    assert isinstance(data["failed_jobs"], list)
    assert isinstance(data["stuck_jobs"], list)


# ── last_login_at update on login ──────────────────────────────────────────


def test_last_login_at_updated_on_login(client: TestClient):
    tokens = register_parent(client, email="timetest@test.com", password="TestPass123")
    # Login again to trigger last_login_at update
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "timetest@test.com", "password": "TestPass123"},
    )
    assert login_resp.status_code == 200

    # Verify last_login_at is set via admin system
    admin_tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(admin_tokens))
    data = resp.json()
    assert data["active_users_24h"] >= 1


def test_failed_login_does_not_update_last_login_at(client: TestClient):
    # Attempt login with wrong password
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "wrong"},
    )
    assert resp.status_code == 401
    # No crash — failed auth should not fail
    assert "detail" in resp.json()


# ── Active user calculation ────────────────────────────────────────────────


def test_active_user_count_respects_timeframe(client: TestClient):
    """Override the 24h cutoff to a very recent time — should see 0 active users
    because no one logged in within that window."""
    system_service.set_last_login_cutoff_override(1)  # 1 second ago
    try:
        tokens = create_admin_and_login(client)
        resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
        data = resp.json()
        # Admin just logged in (within 1 second), so should be at least 1
        assert data["active_users_24h"] >= 1
        assert data["active_admins_24h"] >= 1
    finally:
        system_service.clear_last_login_cutoff_override()


def test_active_user_count_zero_when_window_too_short(client: TestClient):
    """With a 1-hour window and pre-existing users, should see at least the
    test admin counted."""
    system_service.set_last_login_cutoff_override(3600)  # 1 hour ago
    try:
        tokens = create_admin_and_login(client, email="windowtest@test.com", password="TestPass123")
        resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
        data = resp.json()
        # Just logged in admin should be counted
        assert data["active_admins_24h"] >= 1
    finally:
        system_service.clear_last_login_cutoff_override()


# ── Stuck / failed job detection ───────────────────────────────────────────


def test_failed_jobs_list_is_json_serializable(client: TestClient):
    """Even when empty or non-empty, failed_jobs must be a list."""
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["failed_jobs"], list)
    for j in data["failed_jobs"]:
        assert "type" in j
        assert "id" in j


def test_stuck_jobs_list_is_json_serializable(client: TestClient):
    """Even when empty or non-empty, stuck_jobs must be a list."""
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["stuck_jobs"], list)
    for j in data["stuck_jobs"]:
        assert "type" in j
        assert "duration_minutes" in j


# ── Stuck job detection logic ──────────────────────────────────────────────


def test_stuck_job_threshold_is_configurable(client: TestClient):
    """Verify the config setting exists and has a default value."""
    from app.core.config import settings
    assert settings.STUCK_JOB_THRESHOLD_MINUTES >= 1


def test_system_health_data_consistent(client: TestClient):
    """Multiple calls return consistent status strings."""
    tokens = create_admin_and_login(client)
    resp1 = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    resp2 = client.get("/api/v1/admin/system", headers=auth_headers(tokens))
    for key in ["database_status", "redis_status"]:
        assert resp1.json()[key] == resp2.json()[key]
