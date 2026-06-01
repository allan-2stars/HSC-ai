import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit import AuditLog
from tests.conftest import _SessionFactory, auth_headers, register_parent


def _get_logs(action: str) -> list:
    async def _q():
        async with _SessionFactory() as session:
            result = await session.execute(
                select(AuditLog).where(AuditLog.action == action)
            )
            return result.scalars().all()
    return asyncio.run(_q())


def test_registration_creates_audit_log(client: TestClient):
    register_parent(client)
    logs = _get_logs("parent.registered")
    assert len(logs) == 1
    assert logs[0].actor_role == "parent"
    assert logs[0].target_type == "user"


def test_login_creates_audit_log(client: TestClient):
    register_parent(client)
    before = len(_get_logs("user.login"))
    client.post("/api/v1/auth/login", json={"email": "parent@test.com", "password": "TestPass123"})
    assert len(_get_logs("user.login")) == before + 1


def test_student_creation_creates_audit_log(client: TestClient):
    tokens = register_parent(client)
    client.post(
        "/api/v1/parents/students",
        json={"display_name": "Alice", "year_level": 5},
        headers=auth_headers(tokens),
    )
    logs = _get_logs("student.created")
    assert len(logs) == 1
    assert logs[0].actor_role == "parent"
    assert logs[0].target_type == "student_profile"
    assert logs[0].metadata_ == {"display_name": "Alice"}


def test_student_deactivation_creates_audit_log(client: TestClient):
    tokens = register_parent(client)
    student = client.post(
        "/api/v1/parents/students",
        json={"display_name": "Bob", "year_level": 4},
        headers=auth_headers(tokens),
    ).json()
    client.delete(
        f"/api/v1/parents/students/{student['id']}",
        headers=auth_headers(tokens),
    )
    logs = _get_logs("student.deactivated")
    assert len(logs) == 1
