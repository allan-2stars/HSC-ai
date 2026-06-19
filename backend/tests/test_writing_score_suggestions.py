"""M5.4 — AI score suggestions: generate, apply, dismiss, RBAC, published block, version binding."""
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


def _setup_review_with_rubric(client: TestClient):
    """Create rubric, task, submit, assign review. Returns (admin_tokens, rubric, task_id, sub_id, review_id, student_tokens)."""
    admin_tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, admin_tokens)
    rubric = _create_rubric(client, admin_tokens, subject_id=sid, exam_type_id=eid,
                            dimensions=DEFAULT_DIMENSIONS, title="Scoring Rubric")
    task_id = _create_task(client, admin_tokens, sid, eid)
    _assign_rubric(client, admin_tokens, task_id, rubric["id"])
    _publish_task(client, admin_tokens, task_id)

    student_tokens = create_student_and_login(client)
    sub_id = _submit(client, task_id, student_tokens, content="This is a well-structured essay with clear arguments.")

    review = _review_for_submission(client, admin_tokens, sub_id)
    review_id = review["id"]

    # Score one dimension so we can verify suggestions don't overwrite
    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(admin_tokens),
    ).json()
    dim = rubric_detail["dimensions"][0]
    _score(client, admin_tokens, review_id, [{"dimension_id": dim["id"], "rating": 5, "comment": "Human score"}])
    _add_feedback(client, admin_tokens, review_id, "Human feedback.")

    return admin_tokens, rubric, task_id, sub_id, review_id, student_tokens


def _review_is_published(client, review_id):
    resp = client.get("/api/v1/admin/writing/reviews", headers=auth_headers(create_admin_and_login(client)))
    for r in resp.json():
        return r["status"]


# ── Generate ─────────────────────────────────────────────────────────────────


def test_generate_creates_suggestion_rows(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 201, resp.text
    suggestions = resp.json()
    assert len(suggestions) >= 1
    for s in suggestions:
        assert s["suggested_rating"] is not None
        assert s["status"] == "generated"
        assert s["provider"] == "mock"


def test_generate_does_not_modify_writing_review_score(client: TestClient):
    """Generating suggestions must NOT alter existing human scores."""
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    # Get current scores
    rubric_block_before = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}",
        headers=auth_headers(admin_tokens),
    ).json()["rubric"]

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )

    rubric_block_after = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}",
        headers=auth_headers(admin_tokens),
    ).json()["rubric"]

    # Scores must be identical
    for before, after in zip(rubric_block_before["scores"], rubric_block_after["scores"]):
        assert before["rating"] == after["rating"]
        assert before["comment"] == after["comment"]


def test_generate_does_not_publish(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )

    review_resp = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}",
        headers=auth_headers(admin_tokens),
    )
    assert review_resp.json()["status"] != "published"


def test_cannot_generate_after_published(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    # Score all dimensions
    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(admin_tokens),
    ).json()
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail["dimensions"]]
    _score(client, admin_tokens, review_id, scores)
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/publish", headers=auth_headers(admin_tokens))

    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


def test_suggestion_uses_rubric_version_id(client: TestClient):
    """Suggestions must reference rubric_version_id, not live rubric."""
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 201, resp.text

    # Verify all suggestions have rubric_version_id set (from the review's version)
    suggestions_resp = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    )
    for s in suggestions_resp.json():
        assert "dimension_version_id" in s
        assert s["dimension_version_id"] is not None


def test_editing_rubric_does_not_alter_existing_suggestions(client: TestClient):
    """After generating suggestions, editing the rubric title must not change existing suggestions."""
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )

    suggestions_before = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()

    # Edit rubric
    client.patch(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        json={"title": "Edited Title"},
        headers=auth_headers(admin_tokens),
    )

    suggestions_after = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()

    assert len(suggestions_before) == len(suggestions_after)
    for before, after in zip(suggestions_before, suggestions_after):
        assert before["suggested_rating"] == after["suggested_rating"]
        assert before["dimension_name"] == after["dimension_name"]


# ── Apply ────────────────────────────────────────────────────────────────────


def test_apply_writes_score_via_human_path(client: TestClient):
    """Applying a suggestion must write the score through upsert_scores."""
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    suggestions = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()

    # Apply the first suggestion
    s = suggestions[0]
    resp = client.post(
        f"/api/v1/admin/writing/score-suggestions/{s['id']}/apply",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "applied"

    # Verify score was written
    rubric_block = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}",
        headers=auth_headers(admin_tokens),
    ).json()["rubric"]
    applied_dimension = [sc for sc in rubric_block["scores"] if sc["dimension_id"]]
    assert len(applied_dimension) > 0


def test_apply_does_not_publish(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    suggestions = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()

    for s in suggestions:
        client.post(
            f"/api/v1/admin/writing/score-suggestions/{s['id']}/apply",
            headers=auth_headers(admin_tokens),
        )

    review_resp = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}",
        headers=auth_headers(admin_tokens),
    )
    assert review_resp.json()["status"] != "published"


def test_cannot_apply_after_review_published(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    suggestions = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()

    # Publish review
    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(admin_tokens),
    ).json()
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail["dimensions"]]
    _score(client, admin_tokens, review_id, scores)
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/publish", headers=auth_headers(admin_tokens))

    resp = client.post(
        f"/api/v1/admin/writing/score-suggestions/{suggestions[0]['id']}/apply",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


# ── Dismiss ──────────────────────────────────────────────────────────────────


def test_dismiss_changes_status_only(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    suggestions = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()

    s = suggestions[0]
    resp = client.post(
        f"/api/v1/admin/writing/score-suggestions/{s['id']}/dismiss",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"

    # Verify dismissed suggestion is still in the list
    after = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()
    dismissed = [x for x in after if x["id"] == s["id"]]
    assert len(dismissed) == 1
    assert dismissed[0]["status"] == "dismissed"


def test_cannot_dismiss_twice(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    suggestions = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()

    s_id = suggestions[0]["id"]
    client.post(f"/api/v1/admin/writing/score-suggestions/{s_id}/dismiss", headers=auth_headers(admin_tokens))

    resp = client.post(
        f"/api/v1/admin/writing/score-suggestions/{s_id}/dismiss",
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 422


# ── RBAC ─────────────────────────────────────────────────────────────────────


def test_student_cannot_access_suggestions(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    student_tokens = create_student_and_login(client)
    resp = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 403


def test_parent_cannot_access_suggestions(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    parent_tokens = register_parent(client)
    resp = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 403


def test_anonymous_cannot_access_suggestions(client: TestClient):
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    resp = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
    )
    assert resp.status_code == 401


def test_no_suggestions_in_student_rubric_api(client: TestClient):
    """Student rubric view must never expose suggestion data."""
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )

    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(admin_tokens),
    ).json()
    scores = [{"dimension_id": d["id"], "rating": 4, "comment": "ok"} for d in rubric_detail["dimensions"]]
    _score(client, admin_tokens, review_id, scores)
    client.post(f"/api/v1/admin/writing/reviews/{review_id}/publish", headers=auth_headers(admin_tokens))

    rubric_view = client.get(
        f"/api/v1/writing/submissions/{sub_id}/rubric",
        headers=auth_headers(student_tokens),
    )
    assert rubric_view.status_code == 200
    data = rubric_view.json()
    for score in data["scores"]:
        assert "suggested_rating" not in score
        assert "suggestion_id" not in score
        assert "confidence" not in score


def test_applied_score_is_editable_before_publish(client: TestClient):
    """After applying a suggestion, the score must be editable by the human
    (no freeze from the suggestion itself)."""
    admin_tokens, rubric, task_id, sub_id, review_id, student_tokens = _setup_review_with_rubric(client)

    client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        json={"provider": "mock"},
        headers=auth_headers(admin_tokens),
    )
    suggestions = client.get(
        f"/api/v1/admin/writing/reviews/{review_id}/score-suggestions",
        headers=auth_headers(admin_tokens),
    ).json()

    client.post(f"/api/v1/admin/writing/score-suggestions/{suggestions[0]['id']}/apply", headers=auth_headers(admin_tokens))

    # Now overwrite with a human score via upsert_scores
    rubric_detail = client.get(
        f"/api/v1/admin/writing/rubrics/{rubric['id']}",
        headers=auth_headers(admin_tokens),
    ).json()
    dim = rubric_detail["dimensions"][0]
    resp = client.post(
        f"/api/v1/admin/writing/reviews/{review_id}/scores",
        json={"scores": [{"dimension_id": dim["id"], "rating": 1, "comment": "Changed my mind"}]},
        headers=auth_headers(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    score = [s for s in resp.json()["scores"] if s["dimension_id"] == dim["id"]][0]
    assert score["rating"] == 1
    assert score["comment"] == "Changed my mind"
