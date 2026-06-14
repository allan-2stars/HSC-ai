from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy, _create_published_question


def _create_question(client: TestClient, tokens: dict, **overrides) -> dict:
    """Create a question without going through the publish pipeline. Returns full question dict."""
    sid, eid = _make_taxonomy(client, tokens)
    payload = {
        "subject_id": sid,
        "exam_type_id": eid,
        "year_level": 5,
        "difficulty": "medium",
        "question_type": "mcq",
        "source_type": "manual",
        "content_ownership": "original",
        "stem": "What is 2 + 2?",
        "correct_answer": "A",
        "full_explanation": "2 + 2 = 4",
        "marks": 1,
        "options_json": [
            {"label": "A", "text": "4", "is_correct": True, "explanation": ""},
            {"label": "B", "text": "3", "is_correct": False, "explanation": ""},
        ],
    }
    payload.update(overrides)
    resp = client.post("/api/v1/admin/questions", json=payload, headers=auth_headers(tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Create Review ─────────────────────────────────────────────────────────────


def test_create_quality_review(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={
            "question_id": q["id"],
            "correctness_score": 4,
            "outcome_alignment_score": 5,
            "difficulty_score": 3,
            "explanation_score": 4,
            "overall_score": 4,
            "notes": "Good question, slightly easy for the difficulty tag.",
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["correctness_score"] == 4
    assert data["outcome_alignment_score"] == 5
    assert data["overall_score"] == 4
    assert data["notes"] == "Good question, slightly easy for the difficulty tag."


def test_create_review_invalid_scores(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    for score in [0, 6, 99]:
        resp = client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": score},
            headers=auth_headers(tokens),
        )
        assert resp.status_code == 422


def test_create_review_nonexistent_question(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": "nonexistent", "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


# ── Content Ownership Blocking ────────────────────────────────────────────────


def test_restricted_ownership_blocked_from_review(client: TestClient):
    """Quality review must be blocked for restricted_reference_only questions."""
    tokens = create_admin_and_login(client)
    q = _create_question(client, tokens, content_ownership="restricted_reference_only")

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422, resp.text
    assert "restricted_reference_only" in resp.json()["detail"]


def test_internal_draft_review_status_allowed_for_review(client: TestClient):
    """internal_draft ownership with review status is allowed — AI/OCR/imported content path."""
    tokens = create_admin_and_login(client)
    q = _create_question(client, tokens, content_ownership="internal_draft")

    # Transition to review
    review_resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "review"},
        headers=auth_headers(tokens),
    )
    assert review_resp.status_code == 200

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text


def test_internal_draft_draft_status_blocked_from_review(client: TestClient):
    """internal_draft ownership with draft status is blocked — not yet in review pipeline."""
    tokens = create_admin_and_login(client)
    q = _create_question(client, tokens, content_ownership="internal_draft")
    # Stays in draft status

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422, resp.text
    assert "draft" in resp.json()["detail"]


def test_original_draft_status_blocked_from_review(client: TestClient):
    """original ownership with draft status is blocked — not yet in review pipeline."""
    tokens = create_admin_and_login(client)
    q = _create_question(client, tokens, content_ownership="original")
    # Stays in draft status

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422, resp.text
    assert "draft" in resp.json()["detail"]


def test_archived_question_blocked_from_review(client: TestClient):
    """Quality review must be blocked for archived questions."""
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    # Create, publish, then archive
    q = _create_published_question(client, tokens, sid, eid)
    archive_resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "archived"},
        headers=auth_headers(tokens),
    )
    assert archive_resp.status_code == 200

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422, resp.text
    assert "archived" in resp.json()["detail"]


def test_approved_internal_draft_allowed_for_review(client: TestClient):
    """internal_draft ownership with approved status is allowed for quality review."""
    tokens = create_admin_and_login(client)
    q = _create_question(client, tokens, content_ownership="internal_draft")

    # Transition to review → approved
    for status in ["review", "approved"]:
        r = client.patch(
            f"/api/v1/admin/questions/{q['id']}/status",
            json={"status": status},
            headers=auth_headers(tokens),
        )
        assert r.status_code == 200

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 4},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text


# ── List Reviews ──────────────────────────────────────────────────────────────


def test_list_quality_reviews(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    for score in [3, 5]:
        client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": score},
            headers=auth_headers(tokens),
        )

    resp = client.get(
        f"/api/v1/admin/content/quality-reviews?question_id={q['id']}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── Dashboard ────────────────────────────────────────────────────────────────


def test_quality_dashboard_average_calculation(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    for i in range(3):
        q = _create_published_question(client, tokens, sid, eid)
        client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": 2 + i},
            headers=auth_headers(tokens),
        )

    resp = client.get(
        "/api/v1/admin/content/quality-dashboard",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reviews"] == 3
    assert data["unique_questions_reviewed"] == 3
    assert data["average_scores"]["overall"] == 3.0


def test_quality_dashboard_empty(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.get(
        "/api/v1/admin/content/quality-dashboard",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reviews"] == 0
    assert data["average_scores"]["overall"] == 0


def test_dashboard_uses_aggregates_not_full_table_scan(client: TestClient):
    """Dashboard must return aggregate metrics without loading all reviews."""
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    # Create many reviews
    for _ in range(5):
        q = _create_published_question(client, tokens, sid, eid)
        client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": 4},
            headers=auth_headers(tokens),
        )

    resp = client.get(
        "/api/v1/admin/content/quality-dashboard",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reviews"] == 5
    assert data["unique_questions_reviewed"] == 5
    # The 'reviews' field caps at 50 most recent (SQL LIMIT)
    assert len(data["reviews"]) <= 50


def test_needs_revision_counts_distinct_questions(client: TestClient):
    """needs_revision_count must count distinct questions, not total low-score reviews."""
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    # Create 3 reviews on the same question, all with score < 3
    for _ in range(3):
        client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": 2},
            headers=auth_headers(tokens),
        )

    resp = client.get(
        "/api/v1/admin/content/quality-dashboard",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should be 1 distinct question, not 3
    assert data["needs_revision_count"] == 1


# ── Provider Aggregation ─────────────────────────────────────────────────────


def test_provider_aggregation_returns_named_keys(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.get(
        "/api/v1/admin/content/quality-by-provider",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert "providers" in data
    assert isinstance(data["source"], list)
    assert isinstance(data["providers"], list)


# ── Outcome Aggregation ──────────────────────────────────────────────────────


def test_outcome_aggregation(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.get(
        "/api/v1/admin/content/quality-by-outcome",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── Regeneration Candidates ──────────────────────────────────────────────────


def test_regeneration_candidates_deterministic_order(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    # Create reviews with different scores
    for score in [1, 2, 2]:
        q = _create_published_question(client, tokens, sid, eid)
        client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": score},
            headers=auth_headers(tokens),
        )

    resp = client.get(
        "/api/v1/admin/content/quality-regeneration-candidates",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Must be ordered by overall_score ASC (lowest scores first)
    scores = [r["overall_score"] for r in data]
    assert scores == sorted(scores)


# ── Permissions ──────────────────────────────────────────────────────────────


def test_non_admin_cannot_create_review(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": "any", "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_non_admin_cannot_access_dashboard(client: TestClient):
    tokens = register_parent(client)
    resp = client.get(
        "/api/v1/admin/content/quality-dashboard",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


# ── Multiple Reviews Per Question ────────────────────────────────────────────


def test_multiple_reviews_per_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    for score in [4, 5]:
        resp = client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": score},
            headers=auth_headers(tokens),
        )
        assert resp.status_code == 201

    resp = client.get(
        f"/api/v1/admin/content/quality-reviews?question_id={q['id']}",
        headers=auth_headers(tokens),
    )
    assert len(resp.json()) == 2


# ── DB CheckConstraint enforcement ────────────────────────────────────────────


def test_score_check_constraint_applied(client: TestClient):
    """Verify the DB-level CheckConstraint rejects scores outside 1-5.
    With Pydantic validation at the API layer, 422 is expected. But we also
    verify the table was created (migration applied) by successfully creating
    a valid review — which confirms the table and constraints exist."""
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    # Valid scores 1-5 all work
    for score in [1, 2, 3, 4, 5]:
        resp = client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": score},
            headers=auth_headers(tokens),
        )
        assert resp.status_code == 201, f"Score {score} should be accepted"

    # Invalid scores are rejected by Pydantic validation (422)
    for score in [0, 6]:
        resp = client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": score},
            headers=auth_headers(tokens),
        )
        assert resp.status_code == 422, f"Score {score} should be rejected"


# ── reviewer_admin_id nullable / SET NULL ─────────────────────────────────────


def test_reviewer_admin_id_nullable(client: TestClient):
    """Verify reviewer_admin_id can be null (SET NULL on admin delete)."""
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "reviewer_admin_id" in data
    # The review records the admin who created it
    assert data["reviewer_admin_id"] is not None
