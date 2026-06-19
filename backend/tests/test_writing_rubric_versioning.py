"""M5.6 — Rubric versioning: version creation, immutability, historical rendering, backfill, audit."""
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


def _publish_review(client, admin_tokens, review_id):
    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/publish",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Version creation on create ─────────────────────────────────────────────


def test_create_rubric_creates_version_1(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid)

    resp = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/versions",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) >= 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["title"] == rubric["title"]


def test_edit_rubric_title_creates_new_version(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid)

    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        json={"title": "Updated Title"},
        headers=auth_headers(tokens),
    )

    resp = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/versions",
        headers=auth_headers(tokens),
    )
    versions = resp.json()
    assert len(versions) == 2
    # Most recent first
    assert versions[0]["version_number"] == 2
    assert versions[0]["title"] == "Updated Title"
    assert versions[1]["version_number"] == 1
    assert versions[1]["title"] != "Updated Title"


def test_old_version_unchanged_after_edit(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS)
    old_title = rubric["title"]

    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        json={"title": "Changed Title"},
        headers=auth_headers(tokens),
    )

    versions = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/versions",
        headers=auth_headers(tokens),
    ).json()
    assert versions[1]["title"] == old_title
    assert versions[0]["title"] == "Changed Title"


def test_add_dimension_creates_new_version(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS)

    client.post(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions",
        json={"name": "New Dim", "description": "Added later", "display_order": 3},
        headers=auth_headers(tokens),
    )

    versions = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/versions",
        headers=auth_headers(tokens),
    ).json()
    assert len(versions) >= 2  # v1 from create + v2 from add


def test_published_review_renders_old_version(client: TestClient):
    """When a rubric is edited after a review is published, the published
    review must render the old version snapshot, not the live rubric."""
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="Original")
    task_id = _create_task(client, tokens, sid, eid)
    _assign_rubric(client, tokens, task_id, rubric["id"])
    _publish_task(client, tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="My essay.")
    review_id = _review_for_submission(client, tokens, sub_id)["id"]

    # Score each dimension
    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(tokens),
    )
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "Good"} for d in rubric_detail.json()["dimensions"]]
    _score(client, tokens, review_id, scores)
    _add_feedback(client, tokens, review_id)
    _publish_review(client, tokens, review_id)

    # Now edit the rubric
    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        json={"title": "Updated After"},
        headers=auth_headers(tokens),
    )

    rubric_view = client.get(
        f"/api/v1/writing/submissions/{sub_id}/rubric",
        headers=auth_headers(student_tokens),
    )
    assert rubric_view.status_code == 200
    assert rubric_view.json()["rubric_title"] == "Original"
    assert rubric_view.json()["rubric_version_id"] is not None


def test_new_review_uses_latest_version(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="V1 Title")

    # Edit rubric BEFORE any review
    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        json={"title": "V2 Title"},
        headers=auth_headers(tokens),
    )

    task_id = _create_task(client, tokens, sid, eid)
    _assign_rubric(client, tokens, task_id, rubric["id"])
    _publish_task(client, tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="New essay.")
    review_id = _review_for_submission(client, tokens, sub_id)["id"]

    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(tokens),
    )
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "Good"} for d in rubric_detail.json()["dimensions"]]
    _score(client, tokens, review_id, scores)
    _add_feedback(client, tokens, review_id)
    _publish_review(client, tokens, review_id)

    rubric_view = client.get(
        f"/api/v1/writing/submissions/{sub_id}/rubric",
        headers=auth_headers(student_tokens),
    )
    assert rubric_view.json()["rubric_title"] == "V2 Title"


def test_deleted_dimension_visible_in_historical_review(client: TestClient):
    """Deleting a dimension after publish must not remove it from historical view."""
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    dims = DEFAULT_DIMENSIONS + [
        {"name": "To Delete", "description": "Will be removed", "display_order": 3}
    ]
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=dims, title="Dim Test")
    task_id = _create_task(client, tokens, sid, eid)
    _assign_rubric(client, tokens, task_id, rubric["id"])
    _publish_task(client, tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="Essay.")
    review_id = _review_for_submission(client, tokens, sub_id)["id"]

    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(tokens),
    )
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail.json()["dimensions"]]
    _score(client, tokens, review_id, scores)
    _add_feedback(client, tokens, review_id)
    _publish_review(client, tokens, review_id)

    # Delete the "To Delete" dimension
    dim_to_delete = [d for d in rubric_detail.json()["dimensions"] if d["name"] == "To Delete"][0]
    client.delete(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions/{dim_to_delete['id']}",
        headers=auth_headers(tokens),
    )

    rubric_view = client.get(
        f"/api/v1/writing/submissions/{sub_id}/rubric",
        headers=auth_headers(student_tokens),
    )
    assert rubric_view.status_code == 200
    dim_names = [s["name"] for s in rubric_view.json()["scores"]]
    assert "To Delete" in dim_names


def test_reordered_dimensions_do_not_affect_historical_review(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="Order Test")
    task_id = _create_task(client, tokens, sid, eid)
    _assign_rubric(client, tokens, task_id, rubric["id"])
    _publish_task(client, tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="Essay.")
    review_id = _review_for_submission(client, tokens, sub_id)["id"]

    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(tokens),
    )
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail.json()["dimensions"]]
    _score(client, tokens, review_id, scores)
    _add_feedback(client, tokens, review_id)
    _publish_review(client, tokens, review_id)

    original_order = [s["display_order"] for s in client.get(
        f"/api/v1/writing/submissions/{sub_id}/rubric",
        headers=auth_headers(student_tokens),
    ).json()["scores"]]

    # Reorder a dimension
    first_dim = rubric_detail.json()["dimensions"][0]
    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/dimensions/{first_dim['id']}",
        json={"display_order": 99},
        headers=auth_headers(tokens),
    )

    after_order = [s["display_order"] for s in client.get(
        f"/api/v1/writing/submissions/{sub_id}/rubric",
        headers=auth_headers(student_tokens),
    ).json()["scores"]]
    assert original_order == after_order


def test_backfill_binds_published_reviews(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="Backfill")
    task_id = _create_task(client, tokens, sid, eid)
    _assign_rubric(client, tokens, task_id, rubric["id"])
    _publish_task(client, tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="Essay.")
    review_id = _review_for_submission(client, tokens, sub_id)["id"]

    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(tokens),
    )
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail.json()["dimensions"]]
    _score(client, tokens, review_id, scores)
    _add_feedback(client, tokens, review_id)
    _publish_review(client, tokens, review_id)

    rubric_view = client.get(
        f"/api/v1/writing/submissions/{sub_id}/rubric",
        headers=auth_headers(student_tokens),
    )
    assert rubric_view.status_code == 200
    assert rubric_view.json()["rubric_version_id"] is not None


def test_student_sees_historical_version(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="Student View")
    task_id = _create_task(client, tokens, sid, eid)
    _assign_rubric(client, tokens, task_id, rubric["id"])
    _publish_task(client, tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="Essay.")
    review_id = _review_for_submission(client, tokens, sub_id)["id"]

    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(tokens),
    )
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail.json()["dimensions"]]
    _score(client, tokens, review_id, scores)
    _add_feedback(client, tokens, review_id)
    _publish_review(client, tokens, review_id)

    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        json={"title": "Modified"},
        headers=auth_headers(tokens),
    )

    resp = client.get(
        f"/api/v1/writing/submissions/{sub_id}/rubric",
        headers=auth_headers(student_tokens),
    )
    assert resp.json()["rubric_title"] == "Student View"


def test_parent_sees_historical_version(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="Parent View")
    task_id = _create_task(client, tokens, sid, eid)
    _assign_rubric(client, tokens, task_id, rubric["id"])
    _publish_task(client, tokens, task_id)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens=parent_tokens)
    students_resp = client.get("/api/v1/parents/students", headers=auth_headers(parent_tokens))
    student_id = students_resp.json()[0]["id"]

    sub_id = _submit(client, task_id, student_tokens, content="Essay.")
    review_id = _review_for_submission(client, tokens, sub_id)["id"]

    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(tokens),
    )
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail.json()["dimensions"]]
    _score(client, tokens, review_id, scores)
    _add_feedback(client, tokens, review_id)
    _publish_review(client, tokens, review_id)

    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        json={"title": "Not For Parent"},
        headers=auth_headers(tokens),
    )

    resp = client.get(
        f"/api/v1/parents/students/{student_id}/writing/{sub_id}/rubric",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["rubric_title"] == "Parent View"


def test_admin_can_inspect_version_history(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    rubric = _create_rubric(client, tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS)

    for title in ["Rubric A", "Rubric B", "Rubric C"]:
        client.patch(
            f"/api/v1/admin/writing/rubrics/{rubric['id']}",
            json={"title": title},
            headers=auth_headers(tokens),
        )

    resp = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}/versions",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 4  # v1 (create) + 3 edits
    assert versions[0]["version_number"] == 4
    assert versions[0]["title"] == "Rubric C"
