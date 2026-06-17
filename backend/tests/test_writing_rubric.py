"""M5.2 — Writing rubrics: templates, dimensions, reviewer scoring, student/parent view, audit."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.audit import AuditLog
from tests.conftest import (
    _run,
    _SessionFactory,
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy
from tests.test_curriculum import _create_framework
from tests.test_writing import _start_writing
from tests.test_writing_review import _submit, _review_for_submission


DEFAULT_DIMENSIONS = [
    {"name": "Ideas", "description": "Quality of ideas", "display_order": 1},
    {"name": "Structure", "description": "Organisation", "display_order": 2},
]


# ── helpers ──────────────────────────────────────────────────────────────────


def _create_rubric(
    client: TestClient,
    admin_tokens: dict,
    *,
    subject_id: str | None = None,
    exam_type_id: str | None = None,
    framework_id: str | None = None,
    dimensions: list | None = None,
    active: bool = True,
    title: str = "Selective Writing Rubric",
) -> dict:
    body = {
        "title": title,
        "subject_id": subject_id,
        "exam_type_id": exam_type_id,
        "framework_id": framework_id,
        "active": active,
    }
    if dimensions is not None:
        body["dimensions"] = dimensions
    resp = client.post("/api/v1/admin/writing/rubrics", json=body, headers=auth_headers(admin_tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_task(client: TestClient, admin_tokens: dict, sid: str, eid: str) -> str:
    resp = client.post(
        "/api/v1/admin/writing/tasks",
        json={"title": "Rubric Task", "prompt": "Write.", "subject_id": sid, "exam_type_id": eid},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _assign_rubric(client: TestClient, admin_tokens: dict, task_id: str, rubric_id: str | None):
    resp = client.post(
        f"/api/v1/admin/writing/tasks/{task_id}/rubric",
        json={"rubric_id": rubric_id},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _publish_task(client: TestClient, admin_tokens: dict, task_id: str):
    resp = client.patch(
        f"/api/v1/admin/writing/tasks/{task_id}/publish", headers=auth_headers(admin_tokens)
    )
    assert resp.status_code == 200, resp.text


def _setup_task_with_rubric(client: TestClient):
    """Returns (admin_tokens, sid, eid, rubric, task_id) with rubric assigned and task published."""
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, subject_id=sid, exam_type_id=eid, dimensions=DEFAULT_DIMENSIONS)
    task_id = _create_task(client, admin_tokens, sid, eid)
    _assign_rubric(client, admin_tokens, task_id, rubric["id"])
    _publish_task(client, admin_tokens, task_id)
    return admin_tokens, sid, eid, rubric, task_id


def _score(client, admin_tokens, review_id, scores):
    return client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/scores",
        json={"scores": scores},
        headers=auth_headers(admin_tokens),
    )


def _add_feedback(client, admin_tokens, review_id, comment="Overall feedback."):
    return client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/feedback",
        json={"overall_comment": comment},
        headers=auth_headers(admin_tokens),
    )


# ── Rubric CRUD ──────────────────────────────────────────────────────────────


def test_admin_can_create_rubric_with_dimensions(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, subject_id=sid, exam_type_id=eid, dimensions=DEFAULT_DIMENSIONS)
    assert rubric["title"] == "Selective Writing Rubric"
    assert rubric["active"] is True
    assert [d["name"] for d in rubric["dimensions"]] == ["Ideas", "Structure"]
    assert rubric["dimensions"][0]["display_order"] == 1


def test_admin_can_create_rubric_with_framework_fk(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    fw = _create_framework(client, admin_tokens, name="Selective 2026")
    rubric = _create_rubric(client, admin_tokens, framework_id=fw["id"], dimensions=DEFAULT_DIMENSIONS)
    assert rubric["framework_id"] == fw["id"]


def test_admin_can_list_rubrics(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    resp = client.get("/api/v1/admin/writing/rubrics", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_admin_can_filter_rubrics_by_active(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS, active=True, title="Active R")
    _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS, active=False, title="Inactive R")
    resp = client.get("/api/v1/admin/writing/rubrics?active=true", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    assert all(r["active"] for r in resp.json())


def test_admin_can_get_rubric_detail(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    resp = client.get(f"/api/v1/admin/writing/rubrics/{rubric['id']}", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200
    assert len(resp.json()["dimensions"]) == 2


def test_admin_can_edit_rubric(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    resp = client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        json={"title": "Renamed Rubric", "active": False},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Renamed Rubric"
    assert resp.json()["active"] is False


def test_admin_can_add_dimension(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    resp = client.post(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions",
        json={"name": "Vocabulary", "description": "Word choice", "display_order": 3},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "Vocabulary"


def test_admin_can_edit_dimension(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    dim_id = rubric["dimensions"][0]["id"]
    resp = client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions/{dim_id}",
        json={"name": "Ideas & Content"},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Ideas & Content"


def test_admin_can_delete_dimension_without_scores(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    dim_id = rubric["dimensions"][1]["id"]
    resp = client.delete(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions/{dim_id}",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 204, resp.text


# ── Rubric assignment ────────────────────────────────────────────────────────


def test_admin_can_assign_and_clear_rubric_on_task(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    task_id = _create_task(client, admin_tokens, sid, eid)

    assigned = _assign_rubric(client, admin_tokens, task_id, rubric["id"])
    assert assigned["rubric_id"] == rubric["id"]

    cleared = _assign_rubric(client, admin_tokens, task_id, None)
    assert cleared["rubric_id"] is None


# ── Reviewer scoring ─────────────────────────────────────────────────────────


def test_admin_can_score_submission(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    scores = [
        {"dimension_id": rubric["dimensions"][0]["id"], "rating": 4, "comment": "Strong ideas."},
        {"dimension_id": rubric["dimensions"][1]["id"], "rating": 3, "comment": "Decent structure."},
    ]
    resp = _score(client, admin_tokens, review["id"], scores)
    assert resp.status_code == 200, resp.text
    returned = {s["dimension_id"]: s for s in resp.json()["scores"]}
    assert returned[rubric["dimensions"][0]["id"]]["rating"] == 4


def test_scoring_is_upsert(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    dim_id = rubric["dimensions"][0]["id"]

    _score(client, admin_tokens, review["id"], [{"dimension_id": dim_id, "rating": 2, "comment": "First."}])
    _score(client, admin_tokens, review["id"], [{"dimension_id": dim_id, "rating": 5, "comment": "Revised."}])

    detail = client.get(
        f"/api/v1/admin/writing/reviews/{review['id']}", headers=auth_headers(admin_tokens)
    ).json()
    scores = {s["dimension_id"]: s for s in detail["rubric"]["scores"] if s.get("rating") is not None}
    assert scores[dim_id]["rating"] == 5
    assert scores[dim_id]["comment"] == "Revised."


def test_score_rating_out_of_range_rejected(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    dim_id = rubric["dimensions"][0]["id"]

    assert _score(client, admin_tokens, review["id"], [{"dimension_id": dim_id, "rating": 6, "comment": "x"}]).status_code == 422
    assert _score(client, admin_tokens, review["id"], [{"dimension_id": dim_id, "rating": 0, "comment": "x"}]).status_code == 422


def test_score_rejects_dimension_from_other_rubric(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    other_rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS, title="Other")
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    resp = _score(
        client, admin_tokens, review["id"],
        [{"dimension_id": other_rubric["dimensions"][0]["id"], "rating": 3, "comment": "x"}],
    )
    assert resp.status_code == 422


def test_score_rejects_when_no_rubric_assigned(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    task_id = _create_task(client, admin_tokens, sid, eid)
    _publish_task(client, admin_tokens, task_id)  # no rubric assigned
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    resp = _score(client, admin_tokens, review["id"], [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 3, "comment": "x"}])
    assert resp.status_code == 422


def test_cannot_score_after_publish(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    full = [
        {"dimension_id": rubric["dimensions"][0]["id"], "rating": 4, "comment": "Good."},
        {"dimension_id": rubric["dimensions"][1]["id"], "rating": 4, "comment": "Good."},
    ]
    _score(client, admin_tokens, review["id"], full)
    _add_feedback(client, admin_tokens, review["id"])
    pub = client.post(f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens))
    assert pub.status_code == 200, pub.text

    resp = _score(client, admin_tokens, review["id"], [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 1, "comment": "late"}])
    assert resp.status_code == 422


# ── Publish gate with rubric ─────────────────────────────────────────────────


def test_publish_blocked_until_all_dimensions_scored(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    # Only one of two dimensions scored.
    _score(client, admin_tokens, review["id"], [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 4, "comment": "Good."}])
    _add_feedback(client, admin_tokens, review["id"])
    resp = client.post(f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens))
    assert resp.status_code == 422


def test_publish_blocked_if_dimension_missing_comment(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    _score(client, admin_tokens, review["id"], [
        {"dimension_id": rubric["dimensions"][0]["id"], "rating": 4, "comment": "Good."},
        {"dimension_id": rubric["dimensions"][1]["id"], "rating": 3, "comment": ""},  # empty comment
    ])
    _add_feedback(client, admin_tokens, review["id"])
    resp = client.post(f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens))
    assert resp.status_code == 422


def test_publish_succeeds_when_rubric_fully_scored(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    _score(client, admin_tokens, review["id"], [
        {"dimension_id": rubric["dimensions"][0]["id"], "rating": 4, "comment": "Strong."},
        {"dimension_id": rubric["dimensions"][1]["id"], "rating": 3, "comment": "Solid."},
    ])
    _add_feedback(client, admin_tokens, review["id"])
    resp = client.post(f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "published"


def test_publish_without_rubric_still_works(client: TestClient):
    """Regression: tasks with no rubric use the M5.1 gate (feedback only)."""
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    task_id = _create_task(client, admin_tokens, sid, eid)
    _publish_task(client, admin_tokens, task_id)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _add_feedback(client, admin_tokens, review["id"])
    resp = client.post(f"/api/v1/admin/writing/reviews/{review['id']}/publish", headers=auth_headers(admin_tokens))
    assert resp.status_code == 200, resp.text


def test_cannot_delete_dimension_with_scores(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    dim_id = rubric["dimensions"][0]["id"]
    _score(client, admin_tokens, review["id"], [{"dimension_id": dim_id, "rating": 3, "comment": "x"}])

    resp = client.delete(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions/{dim_id}",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


# ── Student / parent rubric view ─────────────────────────────────────────────


def _fully_review_and_publish(client, admin_tokens, rubric, review_id):
    _score(client, admin_tokens, review_id, [
        {"dimension_id": rubric["dimensions"][0]["id"], "rating": 5, "comment": "Excellent ideas."},
        {"dimension_id": rubric["dimensions"][1]["id"], "rating": 4, "comment": "Strong structure."},
    ])
    _add_feedback(client, admin_tokens, review_id)
    pub = client.post(f"/api/v1/admin/writing/reviews/{review_id}/publish", headers=auth_headers(admin_tokens))
    assert pub.status_code == 200, pub.text


def test_student_can_view_published_rubric_assessment(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _fully_review_and_publish(client, admin_tokens, rubric, review["id"])

    resp = client.get(
        f"/api/v1/writing/submissions/{submission_id}/rubric", headers=auth_headers(student_tokens)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["rubric_title"] == "Selective Writing Rubric"
    names = [s["name"] for s in data["scores"]]
    assert names == ["Ideas", "Structure"]
    assert data["scores"][0]["rating"] == 5
    assert "official Selective School marking" in data["disclaimer"]


def test_student_cannot_view_unpublished_rubric(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _score(client, admin_tokens, review["id"], [
        {"dimension_id": rubric["dimensions"][0]["id"], "rating": 5, "comment": "x"},
        {"dimension_id": rubric["dimensions"][1]["id"], "rating": 4, "comment": "y"},
    ])
    resp = client.get(
        f"/api/v1/writing/submissions/{submission_id}/rubric", headers=auth_headers(student_tokens)
    )
    assert resp.status_code == 404


def test_student_cannot_view_other_students_rubric(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student1 = create_student_and_login(client)
    submission_id = _submit(client, task_id, student1)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _fully_review_and_publish(client, admin_tokens, rubric, review["id"])

    student2 = create_student_and_login(client)
    resp = client.get(
        f"/api/v1/writing/submissions/{submission_id}/rubric", headers=auth_headers(student2)
    )
    assert resp.status_code == 403


def test_parent_can_view_published_rubric_assessment(client: TestClient):
    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens=parent_tokens)
    student_id = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens)).json()[0]["id"]

    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _fully_review_and_publish(client, admin_tokens, rubric, review["id"])

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/writing/{submission_id}/rubric",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["scores"][0]["rating"] == 5


def test_parent_cannot_view_unpublished_rubric(client: TestClient):
    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens=parent_tokens)
    student_id = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens)).json()[0]["id"]

    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    submission_id = _submit(client, task_id, student_tokens)
    _review_for_submission(client, admin_tokens, submission_id)

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/writing/{submission_id}/rubric",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 404


def test_parent_cannot_view_other_parents_student_rubric(client: TestClient):
    parent1 = register_parent(client, email="rub1@test.com")
    parent2 = register_parent(client, email="rub2@test.com", password="Pass45678")
    s1_tokens = create_student_and_login(client, parent_tokens=parent1)
    create_student_and_login(client, parent_tokens=parent2)
    parent2_student_id = client.get("/api/v1/parents/students", headers=auth_headers(parent2)).json()[0]["id"]

    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    submission_id = _submit(client, task_id, s1_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _fully_review_and_publish(client, admin_tokens, rubric, review["id"])

    resp = client.get(
        f"/api/v1/parents/students/{parent2_student_id}/writing/{submission_id}/rubric",
        headers=auth_headers(parent2),
    )
    assert resp.status_code in (403, 404)


# ── RBAC ─────────────────────────────────────────────────────────────────────


def test_non_admin_cannot_create_rubric(client: TestClient):
    parent_tokens = register_parent(client)
    resp = client.post(
        "/api/v1/admin/writing/rubrics",
        json={"title": "Hack", "dimensions": DEFAULT_DIMENSIONS},
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 403


def test_non_admin_cannot_score(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review['id']}/scores",
        json={"scores": [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 3, "comment": "x"}]},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 403


def test_anonymous_cannot_list_rubrics(client: TestClient):
    resp = client.get("/api/v1/admin/writing/rubrics")
    assert resp.status_code == 401


# ── Audit logging ────────────────────────────────────────────────────────────


def test_rubric_create_is_audited(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)

    async def _fetch():
        async with _SessionFactory() as session:
            result = await session.execute(
                select(AuditLog.action).where(AuditLog.target_id == rubric["id"])
            )
            return [r[0] for r in result.all()]

    assert "writing_rubric.created" in _run(_fetch())


def test_scoring_and_assignment_are_audited(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _score(client, admin_tokens, review["id"], [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 3, "comment": "x"}])

    async def _fetch(target_id):
        async with _SessionFactory() as session:
            result = await session.execute(
                select(AuditLog.action).where(AuditLog.target_id == target_id)
            )
            return [r[0] for r in result.all()]

    assert "writing_review.scored" in _run(_fetch(review["id"]))
    assert "writing_task.rubric_assigned" in _run(_fetch(task_id))


# ── DB-level rating constraint ───────────────────────────────────────────────


# ── M5.2 hardening: dimension audit (H1) ─────────────────────────────────────


def _audit_actions(target_id: str) -> list[str]:
    async def _fetch():
        async with _SessionFactory() as session:
            result = await session.execute(
                select(AuditLog.action).where(AuditLog.target_id == target_id)
            )
            return [r[0] for r in result.all()]
    return _run(_fetch())


def _audit_entries(target_id: str, action: str) -> list:
    async def _fetch():
        async with _SessionFactory() as session:
            result = await session.execute(
                select(AuditLog).where(AuditLog.target_id == target_id, AuditLog.action == action)
            )
            return list(result.scalars().all())
    return _run(_fetch())


def test_dimension_update_is_audited(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    dim_id = rubric["dimensions"][0]["id"]
    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions/{dim_id}",
        json={"name": "Ideas & Content"},
        headers=auth_headers(admin_tokens),
    )
    entries = _audit_entries(rubric["id"], "writing_rubric.updated")
    dim_updates = [e for e in entries if (e.metadata_ or {}).get("dimension_updated") == dim_id]
    assert dim_updates, "expected an audit entry for the dimension update"
    meta = dim_updates[0].metadata_
    assert meta["previous"]["name"] == "Ideas"
    assert meta["new"]["name"] == "Ideas & Content"


def test_dimension_delete_is_audited(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS)
    dim_id = rubric["dimensions"][1]["id"]
    resp = client.delete(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions/{dim_id}",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 204
    entries = _audit_entries(rubric["id"], "writing_rubric.updated")
    deletes = [e for e in entries if (e.metadata_ or {}).get("dimension_deleted") == dim_id]
    assert deletes, "expected an audit entry for the dimension delete"
    assert deletes[0].metadata_["deleted"]["name"] == "Structure"


# ── M5.2 hardening: reassignment policy (M2) ─────────────────────────────────


def test_cannot_reassign_rubric_when_scores_exist(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    other = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS, title="Other")
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _score(client, admin_tokens, review["id"], [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 3, "comment": "x"}])

    resp = client.post(
        f"/api/v1/admin/writing/tasks/{task_id}/rubric",
        json={"rubric_id": other["id"]},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


def test_cannot_clear_rubric_when_scores_exist(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _score(client, admin_tokens, review["id"], [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 3, "comment": "x"}])

    resp = client.post(
        f"/api/v1/admin/writing/tasks/{task_id}/rubric",
        json={"rubric_id": None},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


def test_reassign_same_rubric_is_noop_even_with_scores(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _score(client, admin_tokens, review["id"], [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 3, "comment": "x"}])

    resp = client.post(
        f"/api/v1/admin/writing/tasks/{task_id}/rubric",
        json={"rubric_id": rubric["id"]},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200


def test_cannot_assign_inactive_rubric(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, dimensions=DEFAULT_DIMENSIONS, active=False)
    task_id = _create_task(client, admin_tokens, sid, eid)
    resp = client.post(
        f"/api/v1/admin/writing/tasks/{task_id}/rubric",
        json={"rubric_id": rubric["id"]},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


def test_cannot_assign_rubric_with_no_dimensions(client: TestClient):
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, dimensions=[])
    task_id = _create_task(client, admin_tokens, sid, eid)
    resp = client.post(
        f"/api/v1/admin/writing/tasks/{task_id}/rubric",
        json={"rubric_id": rubric["id"]},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


# ── M5.2 hardening: score provenance (M3) ────────────────────────────────────


def test_score_records_provenance(client: TestClient):
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)
    _score(client, admin_tokens, review["id"], [{"dimension_id": rubric["dimensions"][0]["id"], "rating": 4, "comment": "Good."}])

    from app.models.writing import WritingReviewScore

    async def _fetch():
        async with _SessionFactory() as session:
            result = await session.execute(
                select(WritingReviewScore).where(WritingReviewScore.review_id == review["id"])
            )
            return list(result.scalars().all())

    rows = _run(_fetch())
    assert rows
    assert rows[0].source == "human"
    assert rows[0].created_by_admin_id is not None


def test_rating_check_constraint_at_db_level(client: TestClient):
    """Direct insert of an out-of-range rating must be rejected by the DB CheckConstraint."""
    admin_tokens, sid, eid, rubric, task_id = _setup_task_with_rubric(client)
    student_tokens = create_student_and_login(client)
    submission_id = _submit(client, task_id, student_tokens)
    review = _review_for_submission(client, admin_tokens, submission_id)

    from app.models.writing import WritingReviewScore

    async def _insert_bad():
        async with _SessionFactory() as session:
            session.add(WritingReviewScore(
                review_id=review["id"],
                dimension_id=rubric["dimensions"][0]["id"],
                rating=99,
                comment="bad",
            ))
            await session.commit()

    with pytest.raises(IntegrityError):
        _run(_insert_bad())
