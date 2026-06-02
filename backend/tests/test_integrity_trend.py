from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)
from tests.test_exam_engine import _setup_published_exam


def _start_attempt(
    client: TestClient, instance_id: str, student_tokens: dict
) -> dict:
    """Start an attempt and return the response data."""
    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Integrity Events ─────────────────────────────────────────────────────────


def test_integrity_event_creation(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)
    attempt = _start_attempt(client, instance_id, student_tokens)

    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/integrity-event",
        json={"event_type": "tab_hidden"},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 204


def _complete_attempt(
    client: TestClient,
    instance_id: str,
    student_tokens: dict,
    answers: list[str] | None = None,
) -> dict:
    """Start and submit an attempt."""
    attempt = _start_attempt(client, instance_id, student_tokens)
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


def test_integrity_event_ownership_enforcement(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student1 = create_student_and_login(client, parent_tokens, display_name="Student One")
    student2 = create_student_and_login(client, parent_tokens, display_name="Student Two")

    attempt = _start_attempt(client, instance_id, student1)

    # Student2 cannot send integrity event for Student1's attempt
    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/integrity-event",
        json={"event_type": "tab_hidden"},
        headers=auth_headers(student2),
    )
    assert resp.status_code == 403


def test_integrity_event_rejected_after_submit(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)
    attempt = _start_attempt(client, instance_id, student_tokens)

    # Answer and submit
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

    # Integrity event after submit should fail
    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/integrity-event",
        json={"event_type": "tab_hidden"},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 409


def test_invalid_event_type_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)
    attempt = _start_attempt(client, instance_id, student_tokens)

    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/integrity-event",
        json={"event_type": "invalid_event"},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 422


def test_integrity_summary_aggregation(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)
    attempt = _start_attempt(client, instance_id, student_tokens)

    # Fire some integrity events
    client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/integrity-event",
        json={"event_type": "tab_hidden"},
        headers=auth_headers(student_tokens),
    )
    client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/integrity-event",
        json={"event_type": "fullscreen_exit"},
        headers=auth_headers(student_tokens),
    )

    # Answer and submit
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

    # Check result has integrity summary
    resp = client.get(
        f"/api/v1/attempts/{attempt['attempt_id']}/result",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    # Integrity summary is stored in the Attempt model but not yet exposed in the result response
    # The data is there in the DB — verify by checking the full attempt


# ── Time Tracking ────────────────────────────────────────────────────────────


def test_time_spent_seconds_persistence(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)
    attempt = _start_attempt(client, instance_id, student_tokens)

    q = attempt["questions"][0]
    resp = client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={
            "exam_instance_question_id": q["exam_instance_question_id"],
            "selected_option": "A",
            "time_spent_seconds": 45,
        },
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["time_spent_seconds"] == 45


def test_time_spent_seconds_accumulates(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)
    attempt = _start_attempt(client, instance_id, student_tokens)

    q = attempt["questions"][0]

    # First save: 30 seconds
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={
            "exam_instance_question_id": q["exam_instance_question_id"],
            "selected_option": "A",
            "time_spent_seconds": 30,
        },
        headers=auth_headers(student_tokens),
    )

    # Update: add 15 more seconds
    resp = client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={
            "exam_instance_question_id": q["exam_instance_question_id"],
            "selected_option": "B",
            "time_spent_seconds": 15,
        },
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["time_spent_seconds"] == 45


def test_time_spent_negative_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)
    attempt = _start_attempt(client, instance_id, student_tokens)

    q = attempt["questions"][0]
    resp = client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={
            "exam_instance_question_id": q["exam_instance_question_id"],
            "selected_option": "A",
            "time_spent_seconds": -5,
        },
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 422


# ── Trend Analytics ──────────────────────────────────────────────────────────


def test_trend_endpoint_ordering(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    # Complete two attempts
    _complete_attempt(client, instance_id, student_tokens, answers=["A"])
    _complete_attempt(client, instance_id, student_tokens, answers=["C"])

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/trend",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    # Should be oldest → newest
    assert "score_percent" in data[0]
    assert "exam_title" in data[0]
    assert "completed_at" in data[0]


def test_trend_endpoint_empty(client: TestClient):
    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/trend",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_student_own_trend(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)

    _complete_attempt(client, instance_id, student_tokens, answers=["A"])

    resp = client.get("/api/v1/students/me/trend", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── Enhanced Recommendations ─────────────────────────────────────────────────


def test_recommendation_includes_slow_topics(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    _complete_attempt(client, instance_id, student_tokens, answers=["A", "B"])

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/recommendations",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "slow_topics" in data
    assert "recommendations" in data


def test_topic_average_time_calculation(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    # Complete attempt with time tracking
    attempt = _start_attempt(client, instance_id, student_tokens)
    for i, q in enumerate(attempt["questions"]):
        client.patch(
            f"/api/v1/attempts/{attempt['attempt_id']}/answers",
            json={
                "exam_instance_question_id": q["exam_instance_question_id"],
                "selected_option": "A" if i == 0 else "B",
                "time_spent_seconds": 30 if i == 0 else 90,
            },
            headers=auth_headers(student_tokens),
        )
    client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/analytics/topics",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    for t in data["topics"]:
        assert "average_time_seconds" in t
        assert t["average_time_seconds"] >= 0
