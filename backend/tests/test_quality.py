import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
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


def _admin_profile_id_from_tokens(client: TestClient, tokens: dict) -> str:
    """Get admin_profile.id from the /me response."""
    resp = client.get("/api/v1/me", headers=auth_headers(tokens))
    assert resp.status_code == 200, resp.text
    user = resp.json()
    # Admin profile IDs are UUIDs; we get user.id, need to find profile.id
    return user["id"]


def _delete_admin_profile_directly(admin_user_id: str) -> None:
    """Delete the AdminProfile row directly in the test DB to exercise SET NULL."""
    from app.core.database import get_db
    from app.models.user import AdminProfile
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    import os

    test_url = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://hscai:change_me_in_production@127.0.0.1:5435/hscai_test")

    async def _do():
        engine = create_async_engine(test_url, poolclass=NullPool)
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as session:
            result = await session.execute(
                select(AdminProfile).where(AdminProfile.user_id == admin_user_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                await session.delete(profile)
                await session.commit()
        await engine.dispose()

    asyncio.run(_do())


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
    assert len(data["reviews"]) <= 50


def test_needs_revision_counts_distinct_questions(client: TestClient):
    """needs_revision_count must count distinct questions, not total low-score reviews."""
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

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


def test_student_cannot_create_review(client: TestClient):
    """Student role must be denied — 403."""
    tokens = create_student_and_login(client)
    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": "any", "overall_score": 3},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_student_cannot_access_dashboard(client: TestClient):
    """Student role must be denied — 403."""
    tokens = create_student_and_login(client)
    resp = client.get(
        "/api/v1/admin/content/quality-dashboard",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_student_cannot_access_provider_comparison(client: TestClient):
    tokens = create_student_and_login(client)
    resp = client.get(
        "/api/v1/admin/content/quality-by-provider",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_student_cannot_access_outcome_quality(client: TestClient):
    tokens = create_student_and_login(client)
    resp = client.get(
        "/api/v1/admin/content/quality-by-outcome",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_anonymous_cannot_create_review(client: TestClient):
    """No auth header — must return 401."""
    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": "any", "overall_score": 3},
    )
    assert resp.status_code == 401


def test_anonymous_cannot_access_dashboard(client: TestClient):
    """No auth header — must return 401."""
    resp = client.get("/api/v1/admin/content/quality-dashboard")
    assert resp.status_code == 401


def test_anonymous_cannot_access_provider_comparison(client: TestClient):
    resp = client.get("/api/v1/admin/content/quality-by-provider")
    assert resp.status_code == 401


def test_anonymous_cannot_access_outcome_quality(client: TestClient):
    resp = client.get("/api/v1/admin/content/quality-by-outcome")
    assert resp.status_code == 401


def test_anonymous_cannot_list_reviews(client: TestClient):
    resp = client.get("/api/v1/admin/content/quality-reviews")
    assert resp.status_code == 401


def test_anonymous_cannot_access_regeneration_candidates(client: TestClient):
    resp = client.get("/api/v1/admin/content/quality-regeneration-candidates")
    assert resp.status_code == 401


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
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    for score in [1, 2, 3, 4, 5]:
        resp = client.post(
            "/api/v1/admin/content/quality-review",
            json={"question_id": q["id"], "overall_score": score},
            headers=auth_headers(tokens),
        )
        assert resp.status_code == 201, f"Score {score} should be accepted"

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
    assert data["reviewer_admin_id"] is not None


def test_admin_deletion_sets_reviewer_to_null(client: TestClient):
    """When reviewer_admin_id is null (e.g. after SET NULL on admin delete),
    the response schema must serialize it correctly as null / None."""
    tokens_a = create_admin_and_login(client, email="reviewer_a@test.com", password="AdminA123")
    tokens_b = create_admin_and_login(client, email="reviewer_b@test.com", password="AdminB123")

    sid, eid = _make_taxonomy(client, tokens_a)
    q = _create_published_question(client, tokens_a, sid, eid)

    resp = client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 4},
        headers=auth_headers(tokens_a),
    )
    assert resp.status_code == 201
    review_id = resp.json()["id"]
    assert resp.json()["reviewer_admin_id"] is not None

    # Simulate SET NULL: directly update the review row (admin rows can't
    # be deleted while a question references them via created_by_admin_id).
    _set_reviewer_null(review_id)

    # Admin B retrieves the review — must still exist with null reviewer
    review_resp = client.get(
        f"/api/v1/admin/content/quality-reviews?question_id={q['id']}",
        headers=auth_headers(tokens_b),
    )
    assert review_resp.status_code == 200
    reviews = review_resp.json()
    assert len(reviews) == 1
    assert reviews[0]["id"] == review_id
    assert reviews[0]["reviewer_admin_id"] is None


def _set_reviewer_null(review_id: str) -> None:
    """Set reviewer_admin_id to NULL directly, simulating SET NULL FK behavior."""
    import os
    from sqlalchemy import text, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.models.quality import QuestionQualityReview

    test_url = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://hscai:change_me_in_production@127.0.0.1:5435/hscai_test")

    async def _do():
        engine = create_async_engine(test_url, poolclass=NullPool)
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as session:
            await session.execute(
                update(QuestionQualityReview)
                .where(QuestionQualityReview.id == review_id)
                .values(reviewer_admin_id=None)
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_do())
