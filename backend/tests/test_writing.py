"""Writing mode — task creation, student response, autosave, submission, RBAC, hardening."""
from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy


def _setup_published_task(client: TestClient) -> tuple[str, str, str, dict]:
    """Create admin, taxonomy, publish a task. Returns (task_id, subject_id, exam_type_id, admin_tokens)."""
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    create_resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Test Task", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    task_id = create_resp.json()["id"]
    client.patch(f"/api/v1/admin/writing/tasks/{task_id}/publish", headers=auth_headers(admin_tokens))
    return task_id, sid, eid, admin_tokens


def _start_writing(client: TestClient, task_id: str, student_tokens: dict) -> str:
    resp = client.post(
        f"/api/v1/writing/tasks/{task_id}/start",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


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


# ── Invalid status query returns 422 ──────────────────────────────────────


def test_admin_list_tasks_invalid_status_returns_422(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/writing/tasks?status=invalid_status", headers=auth_headers(tokens))
    assert resp.status_code == 422


def test_admin_list_submissions_invalid_status_returns_422(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/writing/submissions?status=bad_status", headers=auth_headers(tokens))
    assert resp.status_code == 422


# ── Student: Start, Save, Submit ───────────────────────────────────────────


def test_student_can_start_writing(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
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

    student_tokens = create_student_and_login(client)
    resp = client.post(
        f"/api/v1/writing/tasks/{task_id}/start",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 422


def test_student_can_save_draft(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    resp = client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "My essay draft", "word_count": 3},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "My essay draft"
    # word_count computed server-side
    assert data["word_count"] == 3  # "My essay draft" = 3 words


def test_word_count_computed_server_side(client: TestClient):
    """Server must compute word_count from content, ignoring client value."""
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    # Send word_count=999 but only 2 words actually
    resp = client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "Hello world", "word_count": 999},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["word_count"] == 2  # server-calculated, not 999


def test_student_can_submit(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "Final essay with several words here.", "word_count": 2},
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
    # word_count recomputed on submit
    assert data["word_count"] == 6  # "Final essay with several words here."


def test_student_cannot_edit_after_submit(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    client.post(f"/api/v1/writing/submissions/{sub_id}/submit", headers=auth_headers(student_tokens))

    resp = client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "Edit after submit", "word_count": 3},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 422


# ── Duplicate submission protection ────────────────────────────────────────


def test_duplicate_start_returns_existing_submission(client: TestClient):
    """Starting the same task twice must return the existing submission, not create a duplicate."""
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)

    resp1 = client.post(f"/api/v1/writing/tasks/{task_id}/start", headers=auth_headers(student_tokens))
    assert resp1.status_code == 200
    sub_id = resp1.json()["id"]

    resp2 = client.post(f"/api/v1/writing/tasks/{task_id}/start", headers=auth_headers(student_tokens))
    assert resp2.status_code == 200
    assert resp2.json()["id"] == sub_id  # same submission


# ── Archived task protection ───────────────────────────────────────────────


def test_cannot_save_on_archived_task(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    # Archive the task
    client.patch(f"/api/v1/admin/writing/tasks/{task_id}/archive", headers=auth_headers(admin_tokens))

    resp = client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "Late edit", "word_count": 2},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 422


def test_cannot_submit_to_archived_task(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    client.patch(f"/api/v1/admin/writing/tasks/{task_id}/archive", headers=auth_headers(admin_tokens))

    resp = client.post(f"/api/v1/writing/submissions/{sub_id}/submit", headers=auth_headers(student_tokens))
    assert resp.status_code == 422


# ── Submit-after-save integrity ────────────────────────────────────────────


def test_submit_recomputes_word_count(client: TestClient):
    """Submitting must recompute word count server-side."""
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "Four score and seven", "word_count": 999},
        headers=auth_headers(student_tokens),
    )

    resp = client.post(f"/api/v1/writing/submissions/{sub_id}/submit", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    assert resp.json()["word_count"] == 4  # "Four score and seven"


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
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    for text in ["First draft.", "Second draft.", "Final draft."]:
        resp = client.patch(
            f"/api/v1/writing/submissions/{sub_id}/save",
            json={"content": text, "word_count": 0},
            headers=auth_headers(student_tokens),
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == text

    get_resp = client.get(f"/api/v1/writing/submissions/{sub_id}", headers=auth_headers(student_tokens))
    assert get_resp.json()["content"] == "Final draft."


# ── Admin: Review Submissions ──────────────────────────────────────────────


def test_admin_can_list_all_submissions(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    client.post(f"/api/v1/writing/submissions/{sub_id}/submit", headers=auth_headers(student_tokens))

    resp = client.get("/api/v1/admin/writing/submissions", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    submissions = resp.json()
    assert len(submissions) >= 1
    assert submissions[0]["status"] == "submitted"


def test_admin_submissions_include_content(client: TestClient):
    """Admin submission list must include the essay content field."""
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student_tokens)

    client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": "My essay content here.", "word_count": 0},
        headers=auth_headers(student_tokens),
    )
    client.post(f"/api/v1/writing/submissions/{sub_id}/submit", headers=auth_headers(student_tokens))

    resp = client.get("/api/v1/admin/writing/submissions", headers=auth_headers(admin_tokens))
    submissions = resp.json()
    assert "content" in submissions[0]
    assert submissions[0]["content"] == "My essay content here."


# ── Parent: View Student Writing ───────────────────────────────────────────


def test_parent_can_view_student_writing(client: TestClient):
    parent_tokens = register_parent(client)

    create_student_and_login(client, parent_tokens=parent_tokens)

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
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    parent_tokens = register_parent(client)

    resp = client.post(
        f"/api/v1/writing/tasks/{task_id}/start",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 403


def test_anonymous_cannot_access_writing(client: TestClient):
    resp = client.get("/api/v1/writing/tasks")
    assert resp.status_code == 401


def test_student_cannot_access_other_student_submission(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student1_tokens = create_student_and_login(client)
    sub_id = _start_writing(client, task_id, student1_tokens)

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

    resp = client.get(
        f"/api/v1/parents/students/{student2_id}/writing",
        headers=auth_headers(parent1_tokens),
    )
    assert resp.status_code == 403
