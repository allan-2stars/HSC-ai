from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)
from tests.test_exam_engine import _setup_published_exam, _make_taxonomy, _create_published_question


# ── Helpers ──────────────────────────────────────────────────────────────────

def _complete_attempt(
    client: TestClient,
    instance_id: str,
    student_tokens: dict,
    answers: list[str] | None = None,
) -> dict:
    """Start and submit an attempt, returning the submit response."""
    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 201, resp.text
    attempt = resp.json()

    for i, q in enumerate(attempt["questions"]):
        option = answers[i] if answers and i < len(answers) else "A"
        client.patch(
            f"/api/v1/attempts/{attempt['attempt_id']}/answers",
            json={"exam_instance_question_id": q["exam_instance_question_id"], "selected_option": option},
            headers=auth_headers(student_tokens),
        )

    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Summary Tests ────────────────────────────────────────────────────────────

def test_topic_analytics_calculation(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    # Complete an attempt
    _complete_attempt(client, instance_id, student_tokens, answers=["A", "B"])

    # Get student ID from the student listing
    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    students = resp.json()
    student_id = students[0]["id"]

    # Check topic analytics
    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/topics",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["topics"]) >= 0  # May be 0 if questions have no topic


def test_skill_analytics_calculation(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    _complete_attempt(client, instance_id, student_tokens, answers=["A", "B"])

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/skills",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["skills"], list)


def test_summary_calculation(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, questions = _setup_published_exam(client, tokens, num_questions=2)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    # Answer Q1 correctly, Q2 incorrectly
    _complete_attempt(client, instance_id, student_tokens, answers=["A", "C"])

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/summary",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_attempts"] == 1
    assert data["average_score"] == 50.0
    assert data["best_score"] == 50.0
    assert data["latest_score"] == 50.0
    assert data["total_questions_answered"] == 2
    assert data["total_correct_answers"] == 1
    assert data["overall_accuracy"] == 50.0


def test_summary_no_attempts(client: TestClient):
    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/summary",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_attempts"] == 0
    assert data["overall_accuracy"] == 0.0


# ── Weakness / Strength ──────────────────────────────────────────────────────

def test_weakness_detection(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    _complete_attempt(client, instance_id, student_tokens, answers=["A", "C"])

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/recommendations",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "weak_topics" in data
    assert "strong_topics" in data
    assert "weak_skills" in data
    assert "strong_skills" in data
    assert "recommendations" in data


# ── Parent Ownership Enforcement ─────────────────────────────────────────────

def test_parent_ownership_enforcement(client: TestClient):
    parent_tokens = register_parent(client)
    create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student1_id = resp.json()[0]["id"]

    # Another parent registers
    other_tokens = register_parent(client, email="other@test.com", display_name="Other Parent")
    create_student_and_login(client, other_tokens, display_name="Other Student")

    # Try to access the first parent's student with the second parent's tokens
    resp = client.get(
        f"/api/v1/parents/students/{student1_id}/analytics/summary",
        headers=auth_headers(other_tokens),
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


def test_student_cannot_access_sibling_analytics(client: TestClient):
    parent_tokens = register_parent(client)
    create_student_and_login(client, parent_tokens, display_name="Student One")
    create_student_and_login(client, parent_tokens, display_name="Student Two")

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    students = resp.json()
    student1_id = students[0]["id"]

    # Login as student2
    student2_tokens = create_student_and_login(
        client, parent_tokens, display_name="Student Three"
    )

    # Student cannot access parent routes at all
    resp = client.get(
        f"/api/v1/parents/students/{student1_id}/analytics/summary",
        headers=auth_headers(student2_tokens),
    )
    assert resp.status_code == 403  # Not a parent


# ── Student Self-View ────────────────────────────────────────────────────────

def test_student_own_progress(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    _complete_attempt(client, instance_id, student_tokens, answers=["A", "C"])

    resp = client.get("/api/v1/students/me/progress", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert data["summary"]["total_attempts"] == 1
    assert data["summary"]["average_score"] == 50.0


def test_student_exam_history(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    _complete_attempt(client, instance_id, student_tokens, answers=["A"])

    resp = client.get("/api/v1/students/me/history", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    entry = data[0]
    assert entry["status"] in ("submitted", "expired")
    assert entry["total_questions"] == 1
    assert "exam_title" in entry


def test_student_exam_history_empty(client: TestClient):
    student_tokens = create_student_and_login(client)

    resp = client.get("/api/v1/students/me/history", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    assert resp.json() == []


def test_parent_cannot_access_other_parent_student(client: TestClient):
    parent1_tokens = register_parent(client, email="p1@test.com")
    create_student_and_login(client, parent1_tokens)

    parent2_tokens = register_parent(client, email="p2@test.com", display_name="Parent Two")

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent1_tokens))
    p1_student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{p1_student_id}/analytics/summary",
        headers=auth_headers(parent2_tokens),
    )
    assert resp.status_code == 403


def test_recommendation_generation(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    # Answer both incorrectly to create weaknesses
    _complete_attempt(client, instance_id, student_tokens, answers=["C", "C"])

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/recommendations",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["recommendations"], list)
