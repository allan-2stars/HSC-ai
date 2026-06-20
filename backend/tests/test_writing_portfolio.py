"""M5.8 — Writing Portfolio: ownership, RBAC, exclusions, detail, dispute/reopen flags."""
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


def _setup_with_published_review(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="PF Rubric")
    task_id = _create_task(client, admin_tokens, sid, eid)
    _assign_rubric(client, admin_tokens, task_id, rubric["id"])
    _publish_task(client, admin_tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="Portfolio essay content.")
    review_id = _review_for_submission(client, admin_tokens, sub_id)["id"]

    rubric_detail = client.get(f"/api/v1/admin/writing/rubrics/{rubric['id']}", headers=auth_headers(admin_tokens)).json()
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "Good"} for d in rubric_detail["dimensions"]]
    _score(client, admin_tokens, review_id, scores)
    _add_feedback(client, admin_tokens, review_id, "Nice work.")
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/publish", headers=auth_headers(admin_tokens))
    return admin_tokens, student_tokens, sub_id, review_id


# ── Portfolio list ────────────────────────────────────────────────────────


def test_student_sees_own_portfolio(client: TestClient):
    admin_tokens, student_tokens, sub_id, review_id = _setup_with_published_review(client)

    resp = client.get("/api/v1/writing/portfolio/me", headers=auth_headers(student_tokens))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] >= 1
    item = data["items"][0]
    assert item["submission_id"] == sub_id
    assert item["average_rating"] is not None
    assert item["task_title"] is not None


def test_student_empty_portfolio(client: TestClient):
    student_tokens = create_student_and_login(client)
    resp = client.get("/api/v1/writing/portfolio/me", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
    assert resp.json()["items"] == []


def test_portfolio_detail_includes_content_feedback_scores(client: TestClient):
    admin_tokens, student_tokens, sub_id, review_id = _setup_with_published_review(client)

    resp = client.get(f"/api/v1/writing/portfolio/me/items/{sub_id}", headers=auth_headers(student_tokens))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["submitted_content"] == "Portfolio essay content."
    assert data["feedback"] is not None
    assert data["feedback"]["overall_comment"] == "Nice work."
    assert len(data["scores"]) >= 1
    assert data["scores"][0]["rating"] == 4
    assert data["disclaimer"] is not None


def test_portfolio_detail_has_dispute_flags(client: TestClient):
    admin_tokens, student_tokens, sub_id, review_id = _setup_with_published_review(client)

    # Create a dispute
    client.post(f"/api/v1/writing/submissions/{sub_id}/disputes", json={"reason": "Flag."}, headers=auth_headers(student_tokens))

    resp = client.get("/api/v1/writing/portfolio/me", headers=auth_headers(student_tokens))
    items = resp.json()["items"]
    assert items[0]["has_dispute"] is True


def test_anonymous_cannot_access_portfolio(client: TestClient):
    resp = client.get("/api/v1/writing/portfolio/me")
    assert resp.status_code == 401


# ── Parent portfolio ──────────────────────────────────────────────────────


def test_parent_sees_child_portfolio(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, subject_id=sid, exam_type_id=eid, dimensions=DEFAULT_DIMENSIONS)
    task_id = _create_task(client, admin_tokens, sid, eid)
    _assign_rubric(client, admin_tokens, task_id, rubric["id"])
    _publish_task(client, admin_tokens, task_id)

    parent_tokens = register_parent(client, email="pf_parent@test.com")
    student_tokens = create_student_and_login(client, parent_tokens=parent_tokens)
    sub_id = _submit(client, task_id, student_tokens, content="Child essay.")
    review_id = _review_for_submission(client, admin_tokens, sub_id)["id"]
    rubric_detail = client.get(f"/api/v1/admin/writing/rubrics/{rubric['id']}", headers=auth_headers(admin_tokens)).json()
    _score(client, admin_tokens, review_id, [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail["dimensions"]])
    _add_feedback(client, admin_tokens, review_id)
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/publish", headers=auth_headers(admin_tokens))

    students = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens)).json()
    student_id = students[0]["id"]

    resp = client.get(f"/api/v1/parents/students/{student_id}/writing/portfolio", headers=auth_headers(parent_tokens))
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_parent_cannot_see_other_child_portfolio(client: TestClient):
    admin_tokens, student_tokens, sub_id, review_id = _setup_with_published_review(client)

    parent_tokens = register_parent(client, email="pf_other@test.com")
    create_student_and_login(client, parent_tokens=parent_tokens)

    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = client.get(f"/api/v1/parents/students/{fake_id}/writing/portfolio", headers=auth_headers(parent_tokens))
    assert resp.status_code == 403


# ── Admin portfolio ───────────────────────────────────────────────────────


def test_admin_can_inspect_student_portfolio(client: TestClient):
    admin_tokens, student_tokens, sub_id, review_id = _setup_with_published_review(client)

    # Get student_id from submissions list
    subs = client.get("/api/v1/admin/writing/submissions", headers=auth_headers(admin_tokens)).json()
    student_id = subs[0]["student_id"]

    resp = client.get(f"/api/v1/admin/writing/portfolio/students/{student_id}", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_admin_can_view_portfolio_detail(client: TestClient):
    admin_tokens, student_tokens, sub_id, review_id = _setup_with_published_review(client)

    subs = client.get("/api/v1/admin/writing/submissions", headers=auth_headers(admin_tokens)).json()
    student_id = subs[0]["student_id"]

    resp = client.get(
        f"/api/v1/admin/writing/portfolio/students/{student_id}/items/{sub_id}",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["submitted_content"] is not None


# ── Published-only guard ──────────────────────────────────────────────────


def test_unpublished_not_in_portfolio(client: TestClient):
    """Submissions without a published review must not appear in portfolio."""
    student_tokens = create_student_and_login(client)
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, subject_id=sid, exam_type_id=eid, dimensions=DEFAULT_DIMENSIONS)
    task_id = _create_task(client, admin_tokens, sid, eid)
    _assign_rubric(client, admin_tokens, task_id, rubric["id"])
    _publish_task(client, admin_tokens, task_id)

    sub_id = _submit(client, task_id, student_tokens, content="Unpublished.")
    # Do NOT score or publish this review

    resp = client.get("/api/v1/writing/portfolio/me", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_student_portfolio_detail_403_for_other_student(client: TestClient):
    admin_tokens, student_tokens, sub_id, review_id = _setup_with_published_review(client)
    other_tokens = create_student_and_login(client)

    resp = client.get(f"/api/v1/writing/portfolio/me/items/{sub_id}", headers=auth_headers(other_tokens))
    assert resp.status_code == 404  # Not their submission
