from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy, _create_published_question


def _create_draft_question(
    client: TestClient, tokens: dict, subject_id: str, exam_type_id: str
) -> dict:
    resp = client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": subject_id, "exam_type_id": exam_type_id,
            "year_level": 5, "difficulty": "medium", "question_type": "mcq",
            "source_type": "manual", "content_ownership": "original",
            "stem": "Draft question: 2+2=?", "correct_answer": "A",
            "full_explanation": "2+2=4", "marks": 1,
            "options_json": [
                {"label": "A", "text": "4", "is_correct": True, "explanation": ""},
                {"label": "B", "text": "3", "is_correct": False, "explanation": ""},
            ],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Lifecycle Transitions ────────────────────────────────────────────────────

def test_submit_draft_for_review(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_draft_question(client, tokens, sid, eid)
    assert q["status"] == "draft"

    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/submit-review",
        json={"quality_score": 4, "review_notes": "Looks good"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "review"
    assert data["quality_score"] == 4
    assert data["review_notes"] == "Looks good"


def test_approve_review_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_draft_question(client, tokens, sid, eid)

    client.post(
        f"/api/v1/admin/content/questions/{q['id']}/submit-review",
        json={},
        headers=auth_headers(tokens),
    )

    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/approve",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_publish_approved_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_draft_question(client, tokens, sid, eid)

    client.post(
        f"/api/v1/admin/content/questions/{q['id']}/submit-review",
        json={},
        headers=auth_headers(tokens),
    )
    client.post(
        f"/api/v1/admin/content/questions/{q['id']}/approve",
        headers=auth_headers(tokens),
    )

    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/publish",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


def test_archive_published_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)
    assert q["status"] == "published"

    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/archive",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_invalid_transitions_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_draft_question(client, tokens, sid, eid)

    # Cannot publish directly from draft
    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/publish",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422

    # Cannot approve directly from draft
    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/approve",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


# ── Review Queue ─────────────────────────────────────────────────────────────

def test_review_queue_lists_pending_questions(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    _create_draft_question(client, tokens, sid, eid)
    q2 = _create_draft_question(client, tokens, sid, eid)
    client.post(
        f"/api/v1/admin/content/questions/{q2['id']}/submit-review",
        json={},
        headers=auth_headers(tokens),
    )

    resp = client.get(
        "/api/v1/admin/content/review",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2  # draft and review questions


def test_review_queue_filter_by_status(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    q = _create_draft_question(client, tokens, sid, eid)
    client.post(
        f"/api/v1/admin/content/questions/{q['id']}/submit-review",
        json={},
        headers=auth_headers(tokens),
    )

    resp = client.get(
        "/api/v1/admin/content/review?status=review",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["status"] == "review"


def test_review_queue_filter_by_source(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    _create_draft_question(client, tokens, sid, eid)

    resp = client.get(
        "/api/v1/admin/content/review?source_type=manual",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["source_type"] == "manual"


# ── Bulk Actions ─────────────────────────────────────────────────────────────

def test_bulk_approve(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    q1 = _create_draft_question(client, tokens, sid, eid)
    q2 = _create_draft_question(client, tokens, sid, eid)

    client.post(
        f"/api/v1/admin/content/questions/{q1['id']}/submit-review",
        json={},
        headers=auth_headers(tokens),
    )
    client.post(
        f"/api/v1/admin/content/questions/{q2['id']}/submit-review",
        json={},
        headers=auth_headers(tokens),
    )

    resp = client.post(
        "/api/v1/admin/content/bulk-action",
        json={"question_ids": [q1["id"], q2["id"]], "action": "approve"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["affected"] == 2


# ── Content Stats ────────────────────────────────────────────────────────────

def test_content_stats_endpoint(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    _create_draft_question(client, tokens, sid, eid)
    q = _create_published_question(client, tokens, sid, eid)

    resp = client.get(
        "/api/v1/admin/content/stats",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert "draft" in data["by_status"]
    assert "published" in data["by_status"]
    assert "manual" in data["by_source"]
    assert "published_this_week" in data
    assert "published_this_month" in data


# ── Permissions ──────────────────────────────────────────────────────────────

def test_non_admin_cannot_submit_review(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_draft_question(client, tokens, sid, eid)

    parent_tokens = register_parent(client)
    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/submit-review",
        json={},
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 403


def test_non_admin_cannot_access_review_queue(client: TestClient):
    parent_tokens = register_parent(client)
    resp = client.get(
        "/api/v1/admin/content/review",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 403


# ── Quality Score Validation ─────────────────────────────────────────────────

def test_quality_score_bounds(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_draft_question(client, tokens, sid, eid)

    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/submit-review",
        json={"quality_score": 7},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422

    resp = client.post(
        f"/api/v1/admin/content/questions/{q['id']}/submit-review",
        json={"quality_score": 0},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422
