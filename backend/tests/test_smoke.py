"""Smoke tests for M4.7C-0 — verify seed data and route accessibility."""
from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)


def test_seed_data_exists_after_login(client: TestClient):
    """Verify that basic auth and user flows work."""
    # Parent can register and login
    tokens = register_parent(client, email="smoke@test.com")
    assert "access_token" in tokens

    # Can see user info
    resp = client.get("/api/v1/me", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["role"] == "parent"


def test_student_can_start_exam(client: TestClient):
    """Verify a student can list available exams after setup."""
    tokens = create_admin_and_login(client)

    # Set up a minimal published exam
    from tests.test_exam_engine import _setup_published_exam
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    # Student can see available exams
    student_tokens = create_student_and_login(client)
    resp = client.get("/api/v1/exams/available", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1

    # Student can start the exam
    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 201, resp.text
    attempt = resp.json()
    assert attempt["total_questions"] == 1
    assert len(attempt["questions"]) == 1


def test_parent_dashboard_accessible(client: TestClient):
    """Verify parent analytics routes are accessible."""
    from tests.test_exam_engine import _setup_published_exam

    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    # Complete one attempt for the student
    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()
    q = attempt["questions"][0]
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q["exam_instance_question_id"], "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )
    client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )

    # Get parent's student list
    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    assert resp.status_code == 200
    students = resp.json()
    assert len(students) >= 1

    student_id = students[0]["id"]

    # Dashboard summary works
    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/summary",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["total_attempts"] >= 1


def test_admin_curriculum_accessible(client: TestClient):
    """Verify admin curriculum routes work."""
    tokens = create_admin_and_login(client)

    resp = client.get("/api/v1/curriculum/frameworks", headers=auth_headers(tokens))
    assert resp.status_code == 200

    resp = client.get("/api/v1/curriculum/dashboard", headers=auth_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_frameworks" in data
    assert "top_gaps" in data
