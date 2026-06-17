"""M5.1 — Human review workflow: reviews, versioned feedback, publish gate, visibility, audit."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError

from app.models.audit import AuditLog
from app.models.writing import WritingFeedback
from tests.conftest import (
    _run,
    _SessionFactory,
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)
from tests.test_writing import _setup_published_task, _start_writing


# ── helpers ─────────────────────────────────────────────────────────────────


def _submit(client: TestClient, task_id: str, student_tokens: dict, content: str = "My essay.") -> str:
    """Start, save, and submit a writing response. Returns the submission id."""
    sub_id = _start_writing(client, task_id, student_tokens)
    client.patch(
        f"/api/v1/writing/submissions/{sub_id}/save",
        json={"content": content, "word_count": 0},
        headers=auth_headers(student_tokens),
    )
    resp = client.post(
        f"/api/v1/writing/submissions/{sub_id}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    return sub_id


def _review_for_submission(client: TestClient, admin_tokens: dict, submission_id: str) -> dict:
    resp = client.get("/api/v1/admin/writing/reviews", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200, resp.text
    for r in resp.json():
        if r["submission_id"] == submission_id:
            return r
    raise AssertionError(f"No review found for submission {submission_id}")


# ── Review auto-creation on submit ───────────────────────────────────────────


def test_review_created_pending_on_submit(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)

    review = _review_for_submission(client, admin_tokens, submission_id)
    assert review["status"] == "pending"
    assert review["reviewer_admin_id"] is None
    assert review["latest_feedback_version"] is None


# ── Admin review queue ───────────────────────────────────────────────────────


def test_admin_can_list_review_queue(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    _submit(client, task_id, student_tokens)

    resp = client.get("/api/v1/admin/writing/reviews", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_review_queue_filter_by_status(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    _submit(client, task_id, student_tokens)

    resp = client.get(
        "/api/v1/admin/writing/reviews?status=pending", headers=auth_headers(admin_tokens)
    )
    assert resp.status_code == 200
    assert all(r["status"] == "pending" for r in resp.json())


def test_review_queue_invalid_status_returns_422(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    resp = client.get(
        "/api/v1/admin/writing/reviews?status=bogus", headers=auth_headers(admin_tokens)
    )
    assert resp.status_code == 422


# ── Assignment ───────────────────────────────────────────────────────────────


def test_admin_can_assign_review_to_self(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/assign",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "assigned"
    assert data["reviewer_admin_id"] is not None
    assert data["assigned_at"] is not None


# ── Opening review (under_review) + content visibility ───────────────────────


def test_open_review_transitions_to_under_review_and_returns_content(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens, content="The quick brown fox.")
    review = _review_for_submission(client, admin_tokens, submission_id)

    resp = client.get(
        f"/api/v1/admin/writing/reviews/{review['id']}", headers=auth_headers(admin_tokens)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "under_review"
    assert data["review_started_at"] is not None
    assert data["submission"]["content"] == "The quick brown fox."
    assert data["feedback"] is None


def test_open_review_is_idempotent_after_first_open(client: TestClient):
    """Opening twice must not regress state nor change review_started_at."""
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    first = client.get(
        f"/api/v1/admin/writing/reviews/{review['id']}", headers=auth_headers(admin_tokens)
    ).json()
    second = client.get(
        f"/api/v1/admin/writing/reviews/{review['id']}", headers=auth_headers(admin_tokens)
    ).json()
    assert second["status"] == "under_review"
    assert second["review_started_at"] == first["review_started_at"]


# ── Feedback authoring (versioned, append-only) ──────────────────────────────


def test_feedback_creates_version_one_and_sets_reviewed(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Strong opening, weak conclusion."},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "reviewed"
    assert data["feedback"]["version"] == 1
    assert data["feedback"]["overall_comment"] == "Strong opening, weak conclusion."


def test_feedback_second_version_increments_and_latest_displayed(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "First pass."},
        headers=auth_headers(admin_tokens),
    )
    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Revised feedback."},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["feedback"]["version"] == 2
    assert data["feedback"]["overall_comment"] == "Revised feedback."

    # Detail view shows the latest version
    detail = client.get(
        f"/api/v1/admin/writing/reviews/{review['id']}", headers=auth_headers(admin_tokens)
    ).json()
    assert detail["feedback"]["version"] == 2


def test_feedback_supports_optional_dimensions(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={
            "overall_comment": "Good.",
            "dimensions": [{"name": "Ideas", "comment": "Creative."}],
        },
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["feedback"]["dimensions"] == [{"name": "Ideas", "comment": "Creative."}]


# ── Publish gate ─────────────────────────────────────────────────────────────


def test_cannot_publish_without_feedback(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


def test_admin_can_publish_after_feedback(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Well done."},
        headers=auth_headers(admin_tokens),
    )
    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "published"
    assert data["published_at"] is not None


def test_cannot_publish_twice(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Done."},
        headers=auth_headers(admin_tokens),
    )
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens)
    )
    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens)
    )
    assert resp.status_code == 422


def test_cannot_add_feedback_after_publish(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Done."},
        headers=auth_headers(admin_tokens),
    )
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens)
    )
    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Sneaky edit."},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


# ── Student feedback visibility ──────────────────────────────────────────────


def test_student_cannot_see_unpublished_feedback(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Not yet visible."},
        headers=auth_headers(admin_tokens),
    )

    resp = client.get(
        f"/api/v1/writing/submissions/{submission_id}/feedback",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 404


def test_student_sees_published_feedback_with_disclaimer(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Excellent structure."},
        headers=auth_headers(admin_tokens),
    )
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens)
    )

    resp = client.get(
        f"/api/v1/writing/submissions/{submission_id}/feedback",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["overall_comment"] == "Excellent structure."
    assert data["version"] == 1
    assert "official Selective School marking" in data["disclaimer"]


def test_student_cannot_see_other_students_feedback(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student1 = create_student_and_login(client)
    submission_id = _submit(client, task_id, student1)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Private."},
        headers=auth_headers(admin_tokens),
    )
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens)
    )

    student2 = create_student_and_login(client)
    resp = client.get(
        f"/api/v1/writing/submissions/{submission_id}/feedback",
        headers=auth_headers(student2),
    )
    assert resp.status_code == 403


# ── Parent feedback visibility ───────────────────────────────────────────────


def test_parent_cannot_see_unpublished_feedback(client: TestClient):
    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens=parent_tokens)
    student_id = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens)).json()[0]["id"]

    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Hidden."},
        headers=auth_headers(admin_tokens),
    )

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/writing/{submission_id}/feedback",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 404


def test_parent_sees_published_feedback(client: TestClient):
    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens=parent_tokens)
    student_id = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens)).json()[0]["id"]

    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Visible to parent."},
        headers=auth_headers(admin_tokens),
    )
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens)
    )

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/writing/{submission_id}/feedback",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["overall_comment"] == "Visible to parent."


def test_parent_cannot_see_other_parents_student_feedback(client: TestClient):
    parent1 = register_parent(client, email="rp1@test.com")
    parent2 = register_parent(client, email="rp2@test.com", password="Pass45678")
    s1_tokens = create_student_and_login(client, parent_tokens=parent1)
    create_student_and_login(client, parent_tokens=parent2)
    parent2_student_id = client.get(
        "/api/v1/parents/students", headers=auth_headers(parent2)
    ).json()[0]["id"]

    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    submission_id = _submit(client, task_id, s1_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "x"},
        headers=auth_headers(admin_tokens),
    )
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens)
    )

    # parent2 asking for their own student but with parent1's submission id → 404/403
    resp = client.get(
        f"/api/v1/parents/students/{parent2_student_id}/writing/{submission_id}/feedback",
        headers=auth_headers(parent2),
    )
    assert resp.status_code in (403, 404)


# ── RBAC ─────────────────────────────────────────────────────────────────────


def test_non_admin_cannot_access_review_queue(client: TestClient):
    parent_tokens = register_parent(client)
    resp = client.get("/api/v1/admin/writing/reviews", headers=auth_headers(parent_tokens))
    assert resp.status_code == 403


def test_anonymous_cannot_access_review_queue(client: TestClient):
    resp = client.get("/api/v1/admin/writing/reviews")
    assert resp.status_code == 401


# ── Audit logging ────────────────────────────────────────────────────────────


def test_lifecycle_actions_are_audited(client: TestClient):
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    review_id = review["id"]

    client.post(f"/api/v1/admin/writing/reviews/{review_id}/assign", headers=auth_headers(admin_tokens))
    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/feedback",
        json={"overall_comment": "Audited."},
        headers=auth_headers(admin_tokens),
    )
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/publish", headers=auth_headers(admin_tokens))

    async def _fetch_actions():
        async with _SessionFactory() as session:
            result = await session.execute(
                select(AuditLog.action).where(AuditLog.target_id == review_id)
            )
            return [row[0] for row in result.all()]

    actions = _run(_fetch_actions())
    assert "writing_review.assigned" in actions
    assert "writing_feedback.created" in actions
    assert "writing_review.published" in actions


def test_review_created_audit_is_system_actor(client: TestClient):
    """writing_review.created must be attributed to 'system' (not the student),
    with submission_id and student_user_id in metadata."""
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    async def _fetch_created_entry():
        async with _SessionFactory() as session:
            result = await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "writing_review.created",
                    AuditLog.target_id == review["id"],
                )
            )
            return result.scalar_one()

    entry = _run(_fetch_created_entry())
    assert entry.actor_role == "system"
    assert entry.actor_user_id is None
    assert entry.metadata_["submission_id"] == submission_id
    assert "student_user_id" in entry.metadata_


# ── DB-level append-only enforcement ─────────────────────────────────────────


def test_feedback_is_append_only_at_db_level(client: TestClient):
    """The DB trigger must reject UPDATE and DELETE on writing_feedback rows."""
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/feedback",
        json={"overall_comment": "Immutable."},
        headers=auth_headers(admin_tokens),
    )

    async def _try_update():
        async with _SessionFactory() as session:
            await session.execute(
                update(WritingFeedback)
                .where(WritingFeedback.review_id == review["id"])
                .values(overall_comment="tampered")
            )
            await session.commit()

    async def _try_delete():
        async with _SessionFactory() as session:
            await session.execute(
                delete(WritingFeedback).where(WritingFeedback.review_id == review["id"])
            )
            await session.commit()

    with pytest.raises(DBAPIError, match="append-only"):
        _run(_try_update())
    with pytest.raises(DBAPIError, match="append-only"):
        _run(_try_delete())
