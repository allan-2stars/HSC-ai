"""M5.5 — Disputes, reopen, republish, publication version history."""
from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy
from tests.test_writing import _start_writing
from tests.test_writing_review import _submit, _review_for_submission
from tests.test_writing_rubric import (
    DEFAULT_DIMENSIONS,
    _add_feedback,
    _assign_rubric,
    _create_rubric,
    _create_task,
    _publish_task,
    _score,
)


def _setup_published_review(client: TestClient):
    """Create rubric, task, submit, review, score, publish. Returns (admin_tokens, student_tokens, rubric, task_id, sub_id, review_id)."""
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="Dispute Rubric")
    task_id = _create_task(client, admin_tokens, sid, eid)
    _assign_rubric(client, admin_tokens, task_id, rubric["id"])
    _publish_task(client, admin_tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="Essay content.")
    review_id = _review_for_submission(client, admin_tokens, sub_id)["id"]

    rubric_detail = client.get(f"/api/v1/admin/writing/rubrics/{rubric['id']}", headers=auth_headers(admin_tokens)).json()
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail["dimensions"]]
    _score(client, admin_tokens, review_id, scores)
    _add_feedback(client, admin_tokens, review_id)
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/publish", headers=auth_headers(admin_tokens))

    return admin_tokens, student_tokens, rubric, task_id, sub_id, review_id


# ── Dispute Creation ────────────────────────────────────────────────────────


def test_student_can_create_dispute(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)

    resp = client.post(
        f"/api/v1/writing/submissions/{sub_id}/disputes",
        json={"reason": "I think my score should be higher."},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "open"
    assert resp.json()["reason"] == "I think my score should be higher."


def test_cannot_dispute_unpublished_review(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, subject_id=sid, exam_type_id=eid, dimensions=DEFAULT_DIMENSIONS)
    task_id = _create_task(client, admin_tokens, sid, eid)
    _assign_rubric(client, admin_tokens, task_id, rubric["id"])
    _publish_task(client, admin_tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="Test.")
    # Not published — review exists but is pending

    resp = client.post(
        f"/api/v1/writing/submissions/{sub_id}/disputes",
        json={"reason": "Too early."},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 422


def test_parent_can_create_dispute(client: TestClient):
    """Parent creates a dispute for their own student's published review."""
    admin_tokens2 = create_admin_and_login(client)
    sid2, eid2 = _make_taxonomy(client, admin_tokens2)
    rubric2 = _create_rubric(client, admin_tokens2, subject_id=sid2, exam_type_id=eid2, dimensions=DEFAULT_DIMENSIONS)
    task_id2 = _create_task(client, admin_tokens2, sid2, eid2)
    _assign_rubric(client, admin_tokens2, task_id2, rubric2["id"])
    _publish_task(client, admin_tokens2, task_id2)

    parent_tokens2 = register_parent(client, email="parent_dispute@test.com")
    student_tokens2 = create_student_and_login(client, parent_tokens=parent_tokens2)
    sub_id2 = _submit(client, task_id2, student_tokens2, content="Essay.")
    review_id2 = _review_for_submission(client, admin_tokens2, sub_id2)["id"]
    rubric_detail2 = client.get(f"/api/v1/admin/writing/rubrics/{rubric2['id']}", headers=auth_headers(admin_tokens2)).json()
    scores2 = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail2["dimensions"]]
    _score(client, admin_tokens2, review_id2, scores2)
    _add_feedback(client, admin_tokens2, review_id2)
    client.post(f"/api/v1/admin/writing/reviews/{review_id2}/publish", headers=auth_headers(admin_tokens2))

    students = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens2)).json()
    student_id = students[0]["id"]

    resp = client.post(
        f"/api/v1/parents/students/{student_id}/writing/{sub_id2}/disputes",
        json={"reason": "Parent wants a regrade."},
        headers=auth_headers(parent_tokens2),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "open"


def test_student_cannot_dispute_other_student_review(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)
    other_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/writing/submissions/{sub_id}/disputes",
        json={"reason": "Hacking."},
        headers=auth_headers(other_tokens),
    )
    assert resp.status_code == 403


# ── Admin: Dispute Management ───────────────────────────────────────────────


def test_admin_can_list_disputes(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)
    client.post(f"/api/v1/writing/submissions/{sub_id}/disputes", json={"reason": "Test."}, headers=auth_headers(student_tokens))

    resp = client.get("/api/v1/admin/writing/disputes", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    disputes = resp.json()
    assert len(disputes) >= 1
    assert disputes[0]["student_name"] is not None


def test_admin_can_accept_dispute(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)
    dispute_resp = client.post(f"/api/v1/writing/submissions/{sub_id}/disputes", json={"reason": "Accept me."}, headers=auth_headers(student_tokens))
    dispute_id = dispute_resp.json()["id"]

    resp = client.post(f"/api/v1/admin/writing/disputes/{dispute_id}/accept", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_admin_can_reject_dispute(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)
    dispute_resp = client.post(f"/api/v1/writing/submissions/{sub_id}/disputes", json={"reason": "Reject me."}, headers=auth_headers(student_tokens))
    dispute_id = dispute_resp.json()["id"]

    resp = client.post(
        f"/api/v1/admin/writing/disputes/{dispute_id}/reject",
        json={"review_notes": "Score is appropriate."},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["admin_response"] == "Score is appropriate."


def test_admin_can_resolve_dispute(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)
    dispute_resp = client.post(f"/api/v1/writing/submissions/{sub_id}/disputes", json={"reason": "Resolve me."}, headers=auth_headers(student_tokens))
    dispute_id = dispute_resp.json()["id"]

    client.post(f"/api/v1/admin/writing/disputes/{dispute_id}/accept", headers=auth_headers(admin_tokens))
    resp = client.post(f"/api/v1/admin/writing/disputes/{dispute_id}/resolve", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


# ── Reopen & Republish ──────────────────────────────────────────────────────


def test_admin_can_reopen_published_review(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)

    resp = client.post(f"/api/v1/admin/writing/reviews/{review_id}/reopen", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["status"] == "reopened"

    # Verify review status changed
    review_resp = client.get(f"/api/v1/admin/writing/reviews/{review_id}", headers=auth_headers(admin_tokens))
    assert review_resp.json()["status"] == "reopened"


def test_reopen_does_not_mutate_submission(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)

    original_sub = client.get(f"/api/v1/writing/submissions/{sub_id}", headers=auth_headers(student_tokens)).json()

    client.post(f"/api/v1/admin/writing/reviews/{review_id}/reopen", headers=auth_headers(admin_tokens))

    after_sub = client.get(f"/api/v1/writing/submissions/{sub_id}", headers=auth_headers(student_tokens)).json()
    assert original_sub["content"] == after_sub["content"]
    assert original_sub["status"] == after_sub["status"]


def test_reopen_allows_editing_feedback(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)

    client.post(f"/api/v1/admin/writing/reviews/{review_id}/reopen", headers=auth_headers(admin_tokens))

    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/feedback",
        json={"overall_comment": "Revised feedback after reopen."},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["feedback"]["overall_comment"] == "Revised feedback after reopen."


def test_republish_creates_publication_version(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)

    client.post(f"/api/v1/admin/writing/reviews/{review_id}/reopen", headers=auth_headers(admin_tokens))
    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/feedback",
        json={"overall_comment": "Revised."},
        headers=auth_headers(admin_tokens),
    )

    resp = client.post(f"/api/v1/admin/writing/reviews/{review_id}/republish", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200, resp.text
    assert resp.json()["publication_version"] >= 1

    versions = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/publication-versions",
        headers=auth_headers(admin_tokens),
    ).json()
    assert len(versions) >= 1


def test_publication_version_history_preserves_original(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)

    # Publish a second time
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/reopen", headers=auth_headers(admin_tokens))
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/feedback", json={"overall_comment": "Revised."}, headers=auth_headers(admin_tokens))
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/republish", headers=auth_headers(admin_tokens))

    versions = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/publication-versions",
        headers=auth_headers(admin_tokens),
    ).json()
    assert len(versions) >= 1
    # Verify the first version still exists
    v1 = [v for v in versions if v["version_number"] == 1]
    assert len(v1) == 1


def test_student_cannot_reopen(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)

    resp = client.post(f"/api/v1/admin/writing/reviews/{review_id}/reopen", headers=auth_headers(student_tokens))
    assert resp.status_code == 403


def test_anonymous_cannot_dispute(client: TestClient):
    admin_tokens, student_tokens, rubric, task_id, sub_id, review_id = _setup_published_review(client)

    resp = client.post(f"/api/v1/writing/submissions/{sub_id}/disputes", json={"reason": "Test."})
    assert resp.status_code == 401
