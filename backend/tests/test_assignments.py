from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)
from tests.test_exam_engine import _setup_published_exam


def _create_assignment(
    client: TestClient,
    student_id: str,
    instance_id: str,
    parent_tokens: dict,
    due_at: str | None = None,
) -> dict:
    resp = client.post(
        f"/api/v1/parents/students/{student_id}/assignments",
        json={"exam_instance_id": instance_id, "due_at": due_at},
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Parent can assign exam ───────────────────────────────────────────────────


def test_parent_can_assign_exam(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    assignment = _create_assignment(client, student_id, instance_id, parent_tokens)
    assert assignment["status"] == "assigned"
    assert assignment["title_snapshot"]
    assert assignment["student_id"] == student_id


# ── Parent cannot assign to another parent's student ─────────────────────────


def test_parent_cannot_assign_other_student(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent1 = register_parent(client, email="p1@test.com")
    create_student_and_login(client, parent1, display_name="P1 Student")

    parent2 = register_parent(client, email="p2@test.com", display_name="Parent Two")
    create_student_and_login(client, parent2, display_name="P2 Student")

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent1))
    p1_student_id = resp.json()[0]["id"]

    # Parent2 tries to assign to Parent1's student
    resp = client.post(
        f"/api/v1/parents/students/{p1_student_id}/assignments",
        json={"exam_instance_id": instance_id},
        headers=auth_headers(parent2),
    )
    assert resp.status_code == 403


# ── Unpublished exam rejected ────────────────────────────────────────────────


def test_cannot_assign_unpublished_exam(client: TestClient):
    from tests.test_exam_engine import _make_taxonomy, _create_published_question

    tokens2 = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens2)
    q = _create_published_question(client, tokens2, sid, eid)

    # Create template and instance but don't publish the instance
    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={"title": "T", "exam_type_id": eid, "duration_minutes": 30},
        headers=auth_headers(tokens2),
    )
    template_id = resp.json()["id"]
    client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections",
        json={"title": "S1", "order_index": 0},
        headers=auth_headers(tokens2),
    )
    section_id = (
        client.get(
            f"/api/v1/admin/exam-templates/{template_id}",
            headers=auth_headers(tokens2),
        )
        .json()["sections"][0]["id"]
    )
    client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections/{section_id}/questions",
        json={"question_id": q["id"]},
        headers=auth_headers(tokens2),
    )
    for s in ["review", "approved", "published"]:
        client.patch(
            f"/api/v1/admin/exam-templates/{template_id}/status",
            json={"status": s},
            headers=auth_headers(tokens2),
        )
    resp = client.post(
        "/api/v1/admin/exam-instances",
        json={"template_id": template_id, "title": "Draft Instance"},
        headers=auth_headers(tokens2),
    )
    draft_instance_id = resp.json()["id"]
    # Don't publish — draft

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    resp = client.post(
        f"/api/v1/parents/students/{student_id}/assignments",
        json={"exam_instance_id": draft_instance_id},
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 409


# ── Student sees own assignments ─────────────────────────────────────────────


def test_student_sees_own_assignments(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    _create_assignment(client, student_id, instance_id, parent_tokens)

    resp = client.get("/api/v1/students/me/assignments", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["status"] == "assigned"
    assert data[0]["title_snapshot"]


# ── Assignment started when attempt starts ───────────────────────────────────


def test_assignment_becomes_started_on_attempt(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    assignment = _create_assignment(client, student_id, instance_id, parent_tokens)

    # Start attempt with assignment linkage
    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start?assignment_id={assignment['id']}",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 201, resp.text

    # Check assignment status
    resp = client.get(
        f"/api/v1/parents/students/{student_id}/assignments",
        headers=auth_headers(parent_tokens),
    )
    data = resp.json()
    started = [a for a in data if a["id"] == assignment["id"]]
    assert len(started) == 1
    assert started[0]["status"] == "started"


# ── Assignment completed when attempt submitted ──────────────────────────────


def test_assignment_becomes_completed_on_attempt_submit(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    assignment = _create_assignment(client, student_id, instance_id, parent_tokens)

    # Start with assignment linkage
    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start?assignment_id={assignment['id']}",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()

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

    # Check assignment status
    resp = client.get(
        f"/api/v1/parents/students/{student_id}/assignments",
        headers=auth_headers(parent_tokens),
    )
    data = resp.json()
    completed = [a for a in data if a["id"] == assignment["id"]]
    assert len(completed) == 1
    assert completed[0]["status"] == "completed"


# ── Overdue logic ────────────────────────────────────────────────────────────


def test_overdue_logic(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    # Create assignment with due date in the past
    past = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
    _create_assignment(client, student_id, instance_id, parent_tokens, due_at=past)

    # List assignments (triggers overdue check)
    resp = client.get(
        f"/api/v1/parents/students/{student_id}/assignments",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    overdue = [a for a in data if a["status"] == "overdue"]
    assert len(overdue) >= 1


# ── Cancellation works ───────────────────────────────────────────────────────


def test_cancellation_works(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    assignment = _create_assignment(client, student_id, instance_id, parent_tokens)

    resp = client.patch(
        f"/api/v1/assignments/{assignment['id']}",
        json={"status": "cancelled"},
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cannot_cancel_completed_assignment(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    assignment = _create_assignment(client, student_id, instance_id, parent_tokens)

    # Complete the assignment via attempt
    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start?assignment_id={assignment['id']}",
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

    # Try to cancel completed assignment
    resp = client.patch(
        f"/api/v1/assignments/{assignment['id']}",
        json={"status": "cancelled"},
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 409


# ── Ownership enforcement ────────────────────────────────────────────────────


def test_parent_cannot_update_other_parent_assignment(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent1 = register_parent(client, email="p1@test.com")
    create_student_and_login(client, parent1)

    parent2 = register_parent(client, email="p2@test.com", display_name="Parent Two")
    create_student_and_login(client, parent2)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent1))
    p1_student_id = resp.json()[0]["id"]

    assignment = _create_assignment(client, p1_student_id, instance_id, parent1)

    # Parent2 tries to cancel Parent1's assignment
    resp = client.patch(
        f"/api/v1/assignments/{assignment['id']}",
        json={"status": "cancelled"},
        headers=auth_headers(parent2),
    )
    assert resp.status_code == 403


# ── Audit logs ───────────────────────────────────────────────────────────────


def test_assignment_audit_logs_created(client: TestClient):
    import asyncio
    from tests.conftest import _SessionFactory

    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    _create_assignment(client, student_id, instance_id, parent_tokens)

    async def _check():
        async with _SessionFactory() as session:
            from sqlalchemy import select as sa_select
            from app.models.audit import AuditLog
            result = await session.execute(
                sa_select(AuditLog).where(
                    AuditLog.action.in_([
                        "assignment_created",
                        "assignment_updated",
                        "assignment_cancelled",
                        "assignment_started",
                        "assignment_completed",
                    ])
                )
            )
            return list(result.scalars().all())

    logs = asyncio.run(_check())
    actions = {log.action for log in logs}
    assert "assignment_created" in actions


# ── Parent assignment summary ───────────────────────────────────────────────


def test_assignment_summary(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    _create_assignment(client, student_id, instance_id, parent_tokens)

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/assignment-summary",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned"] >= 1


# ── Student assignment detail ────────────────────────────────────────────────


def test_student_assignment_detail(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = resp.json()[0]["id"]

    assignment = _create_assignment(client, student_id, instance_id, parent_tokens)

    resp = client.get(
        f"/api/v1/students/me/assignments/{assignment['id']}",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["title_snapshot"]


# ── Student cannot access another student's assignment ───────────────────────


def test_student_cannot_access_other_assignment(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student1 = create_student_and_login(client, parent_tokens, display_name="S1")
    student2 = create_student_and_login(client, parent_tokens, display_name="S2")

    resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    s1_id = resp.json()[0]["id"]

    assignment = _create_assignment(client, s1_id, instance_id, parent_tokens)

    # Student2 tries to view Student1's assignment
    resp = client.get(
        f"/api/v1/students/me/assignments/{assignment['id']}",
        headers=auth_headers(student2),
    )
    assert resp.status_code == 403
