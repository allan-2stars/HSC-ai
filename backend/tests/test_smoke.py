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


# ── M4.8 Pilot Smoke Tests ──────────────────────────────────────────────────


def test_content_pipeline_lifecycle(client: TestClient):
    """Verify the draft→review→approved→published lifecycle works end-to-end."""
    tokens = create_admin_and_login(client)
    sid, eid = (
        __import__("tests.test_exam_engine", fromlist=["_make_taxonomy"])
        ._make_taxonomy(client, tokens)
    )

    # Create a draft question
    resp = client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": sid, "exam_type_id": eid, "year_level": 5,
            "difficulty": "medium", "question_type": "mcq",
            "source_type": "ai", "content_ownership": "original",
            "stem": "Pilot test: What is 2+2?", "correct_answer": "A",
            "full_explanation": "2+2=4", "marks": 1,
            "options_json": [
                {"label": "A", "text": "4", "is_correct": True, "explanation": ""},
                {"label": "B", "text": "3", "is_correct": False, "explanation": ""},
            ],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    q_id = resp.json()["id"]

    # draft → review
    resp = client.post(
        f"/api/v1/admin/content/questions/{q_id}/submit-review",
        json={"quality_score": 4},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "review"

    # review → approve
    resp = client.post(
        f"/api/v1/admin/content/questions/{q_id}/approve",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # approve → publish
    resp = client.post(
        f"/api/v1/admin/content/questions/{q_id}/publish",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


def test_bulk_question_creation_and_publication(client: TestClient):
    """Verify multiple questions can be created and published."""
    tokens = create_admin_and_login(client)
    sid, eid = (
        __import__("tests.test_exam_engine", fromlist=["_make_taxonomy"])
        ._make_taxonomy(client, tokens)
    )

    ids = []
    for i in range(5):
        resp = client.post(
            "/api/v1/admin/questions",
            json={
                "subject_id": sid, "exam_type_id": eid, "year_level": 5,
                "difficulty": "medium", "question_type": "mcq",
                "source_type": "manual", "content_ownership": "original",
                "stem": f"Bulk Q{i}: What is {i}+{i}?", "correct_answer": "A",
                "full_explanation": f"{i}+{i}={i*2}", "marks": 1,
                "options_json": [
                    {"label": "A", "text": str(i*2), "is_correct": True, "explanation": ""},
                    {"label": "B", "text": str(i), "is_correct": False, "explanation": ""},
                ],
            },
            headers=auth_headers(tokens),
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])

    # Bulk approve: submit for review then approve each
    for qid in ids:
        client.post(
            f"/api/v1/admin/content/questions/{qid}/submit-review",
            json={},
            headers=auth_headers(tokens),
        )
        client.post(
            f"/api/v1/admin/content/questions/{qid}/approve",
            headers=auth_headers(tokens),
        )

    # Bulk publish using bulk action
    resp = client.post(
        "/api/v1/admin/content/bulk-action",
        json={"question_ids": ids, "action": "publish"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["affected"] == 5
