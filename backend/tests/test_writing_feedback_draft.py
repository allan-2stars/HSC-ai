"""M5.3 — AI feedback drafts.

AI generates *draft* feedback only. It never assigns rubric scores, never edits
ratings, never publishes, and never overwrites official human feedback. Drafts are
admin/reviewer-only and never exposed to students or parents. Copying a draft into
official feedback is an explicit human action.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.writing import WritingFeedback, WritingFeedbackDraft
from tests.conftest import (
    _run,
    _SessionFactory,
    auth_headers,
    create_student_and_login,
    register_parent,
)
from tests.test_writing import _setup_published_task
from tests.test_writing_review import _review_for_submission, _submit


# ── helpers ─────────────────────────────────────────────────────────────────


def _setup_review(client: TestClient):
    """Published task + submitted response + its (pending) review."""
    task_id, sid, eid, admin_tokens = _setup_published_task(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(
        client, task_id, student_tokens,
        content="The sun rose over the quiet harbour and the sleepy city slowly woke.",
    )
    review = _review_for_submission(client, admin_tokens, submission_id)
    return admin_tokens, student_tokens, review, submission_id


def _generate(client: TestClient, admin_tokens: dict, review_id: str, provider=None):
    body = {} if provider is None else {"provider": provider}
    return client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/ai-draft",
        json=body,
        headers=auth_headers(admin_tokens),
    )


def _drafts_for(review_id: str) -> list[WritingFeedbackDraft]:
    async def _q():
        async with _SessionFactory() as s:
            return list((await s.execute(
                select(WritingFeedbackDraft).where(WritingFeedbackDraft.review_id == review_id)
            )).scalars().all())
    return _run(_q())


def _official_feedback_for(review_id: str) -> list[WritingFeedback]:
    async def _q():
        async with _SessionFactory() as s:
            return list((await s.execute(
                select(WritingFeedback).where(WritingFeedback.review_id == review_id)
            )).scalars().all())
    return _run(_q())


# ── Generation ──────────────────────────────────────────────────────────────


def test_generate_creates_structured_draft(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    resp = _generate(client, admin_tokens, review["id"])
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "generated"
    assert data["review_id"] == review["id"]
    assert data["provider"]
    assert data["prompt_version"]
    fb = data["draft_feedback"]
    assert set(fb.keys()) == {"strengths", "improvements", "next_steps", "overall_feedback"}
    assert isinstance(fb["strengths"], list)
    assert isinstance(fb["improvements"], list)
    assert isinstance(fb["next_steps"], list)
    assert isinstance(fb["overall_feedback"], str) and fb["overall_feedback"].strip()


def test_generate_persists_draft_row(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    _generate(client, admin_tokens, review["id"])
    rows = _drafts_for(review["id"])
    assert len(rows) == 1
    assert rows[0].status == "generated"
    assert rows[0].draft_feedback_json["overall_feedback"]


def test_generate_does_not_create_official_feedback(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    _generate(client, admin_tokens, review["id"])
    assert _official_feedback_for(review["id"]) == []


def test_generate_does_not_publish_review(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    _generate(client, admin_tokens, review["id"])
    queue = client.get("/api/v1/admin/writing/reviews", headers=auth_headers(admin_tokens)).json()
    row = next(r for r in queue if r["id"] == review["id"])
    assert row["status"] != "published"


def test_generate_works_with_rubric_assigned(client: TestClient):
    from tests.test_writing_rubric import _setup_task_with_rubric

    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(
        client, task_id, student_tokens,
        content="A long enough essay describing the harbour at dawn and the waking city.",
    )
    review = _review_for_submission(client, admin_tokens, submission_id)
    resp = _generate(client, admin_tokens, review["id"])
    assert resp.status_code == 201, resp.text


def test_generate_is_audited(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    _generate(client, admin_tokens, review["id"])

    async def _logs():
        async with _SessionFactory() as s:
            return list((await s.execute(
                select(AuditLog).where(AuditLog.action == "writing_feedback_draft.generated")
            )).scalars().all())
    assert len(_run(_logs())) == 1


# ── Access control: admin/reviewer only ─────────────────────────────────────


def test_student_cannot_generate_draft(client: TestClient):
    admin_tokens, student_tokens, review, _ = _setup_review(client)
    resp = _generate(client, student_tokens, review["id"])
    assert resp.status_code in (401, 403)


def test_student_cannot_list_drafts(client: TestClient):
    admin_tokens, student_tokens, review, _ = _setup_review(client)
    _generate(client, admin_tokens, review["id"])
    resp = client.get(
        f"/api/v1/admin/writing/reviews/{review['id']}/ai-drafts",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code in (401, 403)


def test_parent_cannot_list_drafts(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    _generate(client, admin_tokens, review["id"])
    parent = register_parent(client, email="p_draft@test.com")
    resp = client.get(
        f"/api/v1/admin/writing/reviews/{review['id']}/ai-drafts",
        headers=auth_headers(parent),
    )
    assert resp.status_code in (401, 403)


def test_admin_can_list_drafts(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    _generate(client, admin_tokens, review["id"])
    _generate(client, admin_tokens, review["id"])
    resp = client.get(
        f"/api/v1/admin/writing/reviews/{review['id']}/ai-drafts",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── Discard ─────────────────────────────────────────────────────────────────


def test_discard_changes_status(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    draft = _generate(client, admin_tokens, review["id"]).json()
    resp = client.post(
        f"/api/v1/admin/writing/ai-drafts/{draft['id']}/discard",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "discarded"


# ── Accept / copy into official feedback (human action) ─────────────────────


def test_accept_creates_official_feedback(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    draft = _generate(client, admin_tokens, review["id"]).json()
    resp = client.post(
        f"/api/v1/admin/writing/ai-drafts/{draft['id']}/accept",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    fbs = _official_feedback_for(review["id"])
    assert len(fbs) == 1
    assert fbs[0].overall_comment.strip() != ""


def test_accept_marks_draft_accepted(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    draft = _generate(client, admin_tokens, review["id"]).json()
    client.post(
        f"/api/v1/admin/writing/ai-drafts/{draft['id']}/accept",
        headers=auth_headers(admin_tokens),
    )
    rows = _drafts_for(review["id"])
    assert rows[0].status == "accepted"


def test_accept_does_not_publish_review(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    draft = _generate(client, admin_tokens, review["id"]).json()
    client.post(
        f"/api/v1/admin/writing/ai-drafts/{draft['id']}/accept",
        headers=auth_headers(admin_tokens),
    )
    queue = client.get("/api/v1/admin/writing/reviews", headers=auth_headers(admin_tokens)).json()
    row = next(r for r in queue if r["id"] == review["id"])
    assert row["status"] != "published"


def test_cannot_generate_after_publish(client: TestClient):
    admin_tokens, _, review, _ = _setup_review(client)
    draft = _generate(client, admin_tokens, review["id"]).json()
    client.post(
        f"/api/v1/admin/writing/ai-drafts/{draft['id']}/accept",
        headers=auth_headers(admin_tokens),
    )
    pub = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish",
        headers=auth_headers(admin_tokens),
    )
    assert pub.status_code == 200, pub.text
    resp = _generate(client, admin_tokens, review["id"])
    assert resp.status_code == 422


# ── Student/parent never see draft content ──────────────────────────────────


def test_draft_not_exposed_to_student_after_publish(client: TestClient):
    admin_tokens, student_tokens, review, submission_id = _setup_review(client)
    draft = _generate(client, admin_tokens, review["id"]).json()
    client.post(
        f"/api/v1/admin/writing/ai-drafts/{draft['id']}/accept",
        headers=auth_headers(admin_tokens),
    )
    pub = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/publish",
        headers=auth_headers(admin_tokens),
    )
    assert pub.status_code == 200, pub.text
    fb = client.get(
        f"/api/v1/writing/submissions/{submission_id}/feedback",
        headers=auth_headers(student_tokens),
    )
    assert fb.status_code == 200, fb.text
    body = fb.json()
    for k in ("strengths", "improvements", "next_steps", "draft_feedback"):
        assert k not in body
