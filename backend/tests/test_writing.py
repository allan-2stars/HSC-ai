"""Writing mode — task creation, student response, autosave, submission, RBAC."""
from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy


# ── Admin: Create Writing Task ─────────────────────────────────────────────


def test_admin_can_create_writing_task(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={
            "title": "Persuasive Essay",
            "prompt": "Should students wear uniforms? Write a persuasive essay.",
            "instructions": "Use at least 3 arguments. Structure: intro, body, conclusion.",
            "word_limit": 300,
            "recommended_time_minutes": 30,
            "subject_id": sid,
            "exam_type_id": eid,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"] == "Persuasive Essay"
    assert data["status"] == "draft"
    assert data["word_limit"] == 300


def test_admin_can_list_writing_tasks(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Test", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(tokens),
    )

    resp = client.get("/api/v1/admin/writing/tasks", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_admin_can_publish_writing_task(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Publish Me", "prompt": "Write something.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(tokens),
    )
    task_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/admin/writing/tasks/{task_id}/publish",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


# ── Student: Start, Save, Submit ───────────────────────────────────────────


def test_student_can_start_writing(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Start Test", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    task_id = create_resp.json()["id"]
    client.patch(
        f"/api/v1/admin/writing/tasks/{task_id}/publish",
        headers=auth_headers(admin_tokens),
    )

    student_tokens = create_student_and_login(client)
    resp = client.post(
        f"/api/v1/writing/tasks/{task_id}/start",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["writing_task_id"] == task_id
    assert data["status"] == "draft"


def test_student_cannot_start_unpublished_task(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Draft Task", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    task_id = create_resp.json()["id"]
    # Don't publish — stays draft

    student_tokens = create_student_and_login(client)
    resp = client.post(
        f"/api/v1/writing/tasks/{task_id}/start",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 422


def test_student_can_save_draft(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Save Test", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    task_id = create_resp.json()["id"]
    client.patch(f"/api/v1/admin/writing/tasks/{task_id}/publish", headers=auth_headers(admin_tokens))

    student_tokens = create_student_and_login(client)
    start_resp = client.post(
        f"/api/v1/writing/tasks/{task_id}/start",
        headers=auth_headers(student_tokens),
    )
    sub_id = start_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "My essay draft", "word_count": 3},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "My essay draft"
    assert resp.json()["word_count"] == 3


def test_student_can_submit(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Submit Test", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    task_id = create_resp.json()["id"]
    client.patch(f"/api/v1/admin/writing/tasks/{task_id}/publish", headers=auth_headers(admin_tokens))

    student_tokens = create_student_and_login(client)
    start_resp = client.post(
        f"/api/v1/writing/tasks/{task_id}/start",
        headers=auth_headers(student_tokens),
    )
    sub_id = start_resp.json()["id"]

    client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "Final essay", "word_count": 2},
        headers=auth_headers(student_tokens),
    )

    resp = client.post(
        f"/api/v1/writing/submissions/{sub_id}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["submitted_at"] is not None


def test_student_cannot_edit_after_submit(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Immutable Test", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    task_id = create_resp.json()["id"]
    client.patch(f"/api/v1/admin/writing/tasks/{task_id}/publish", headers=auth_headers(admin_tokens))

    student_tokens = create_student_and_login(client)
    start_resp = client.post(
        f"/api/v1/writing/tasks/{task_id}/start",
        headers=auth_headers(student_tokens),
    )
    sub_id = start_resp.json()["id"]

    client.post(f"/api/v1/writing/submissions/{sub_id}/submit", headers=auth_headers(student_tokens))

    resp = client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "Edit after submit", "word_count": 3},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 422


def test_student_can_list_available_tasks(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "List Test", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    client.patch(f"/api/v1/admin/writing/tasks/{create_resp.json()["id"]}/publish", headers=auth_headers(admin_tokens))

    student_tokens = create_student_and_login(client)
    resp = client.get("/api/v1/writing/tasks", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) >= 1
    assert tasks[0]["title"] == "List Test"


def test_autosave_preserves_content(client: TestClient):
    """Multiple saves must preserve the latest content."""
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Autosave Test", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    client.patch(f"/api/v1/admin/writing/tasks/{create_resp.json()["id"]}/publish", headers=auth_headers(admin_tokens))

    student_tokens = create_student_and_login(client)
    start_resp = client.post(
        f"/api/v1/writing/tasks/{create_resp.json()["id"]}/start",
        headers=auth_headers(student_tokens),
    )
    sub_id = start_resp.json()["id"]

    # Simulate 3 autosaves
    for i, text in enumerate(["First draft.", "Second draft.", "Final draft."]):
        resp = client.patch(
            f"/api/v1/writing/submissions/{sub_id}/save",
            json={"content": text, "word_count": 2},
            headers=auth_headers(student_tokens),
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == text

    # Final fetch confirms last save persisted
    get_resp = client.get(
        f"/api/v1/writing/submissions/{sub_id}",
        headers=auth_headers(student_tokens),
    )
    assert get_resp.json()["content"] == "Final draft."


# ── Admin: Review Submissions ──────────────────────────────────────────────


def test_admin_can_list_all_submissions(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Review Test", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    client.patch(f"/api/v1/admin/writing/tasks/{create_resp.json()["id"]}/publish", headers=auth_headers(admin_tokens))

    student_tokens = create_student_and_login(client)
    start_resp = client.post(
        f"/api/v1/writing/tasks/{create_resp.json()["id"]}/start",
        headers=auth_headers(student_tokens),
    )
    client.post(f"/api/v1/writing/submissions/{start_resp.json()["id"]}/submit", headers=auth_headers(student_tokens))

    resp = client.get("/api/v1/admin/writing/submissions", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    submissions = resp.json()
    assert len(submissions) >= 1
    assert submissions[0]["status"] == "submitted"


# ── Parent: View Student Writing ───────────────────────────────────────────


def test_parent_can_view_student_writing(client: TestClient):
    parent_tokens = register_parent(client)

    student_tokens = create_student_and_login(client, parent_tokens=parent_tokens)

    # Get student profile id
    me_resp = client.get("/api/v1/me", headers=auth_headers(student_tokens))
    # Need the student profile ID from the student listing
    students_resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = students_resp.json()[0]["id"]

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/writing",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── RBAC ───────────────────────────────────────────────────────────────────


def test_non_admin_cannot_create_writing_task(client: TestClient):
    tokens = register_parent(client)
    sid, eid = _make_taxonomy(client, create_admin_and_login(client))

    resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Hack", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_non_student_cannot_start_writing(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "RBAC", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    client.patch(f"/api/v1/admin/writing/tasks/{create_resp.json()["id"]}/publish", headers=auth_headers(admin_tokens))

    parent_tokens = register_parent(client)
    resp = client.post(
        f"/api/v1/writing/tasks/{create_resp.json()["id"]}/start",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 403


def test_anonymous_cannot_access_writing(client: TestClient):
    resp = client.get("/api/v1/writing/tasks")
    assert resp.status_code == 401


def test_student_cannot_access_other_student_submission(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)

    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Ownership", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    client.patch(f"/api/v1/admin/writing/tasks/{create_resp.json()["id"]}/publish", headers=auth_headers(admin_tokens))

    student1_tokens = create_student_and_login(client)
    start_resp = client.post(
        f"/api/v1/writing/tasks/{create_resp.json()["id"]}/start",
        headers=auth_headers(student1_tokens),
    )
    sub_id = start_resp.json()["id"]

    student2_tokens = create_student_and_login(client)
    resp = client.get(
        f"/api/v1/writing/submissions/{sub_id}",
        headers=auth_headers(student2_tokens),
    )
    assert resp.status_code == 403


def test_parent_cannot_view_other_parent_student_writing(client: TestClient):
    parent1_tokens = register_parent(client, email="p1@test.com")
    parent2_tokens = register_parent(client, email="p2@test.com", password="Pass45678")

    create_student_and_login(client, parent_tokens=parent1_tokens)
    create_student_and_login(client, parent_tokens=parent2_tokens)
    students2 = client.get("/api/v1/parents/students", headers=auth_headers(parent2_tokens))
    student2_id = students2.json()[0]["id"]

    # Parent 1 tries to view Parent 2's student
    resp = client.get(
        f"/api/v1/parents/students/{student2_id}/writing",
        headers=auth_headers(parent1_tokens),
    )
    assert resp.status_code == 403
