from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy, _create_published_question


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


def test_list_quality_reviews(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid)

    # Create two reviews
    client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 3},
        headers=auth_headers(tokens),
    )
    client.post(
        "/api/v1/admin/content/quality-review",
        json={"question_id": q["id"], "overall_score": 5},
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
    # Average of 2,3,4 = 3.0
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


# ── Provider Aggregation ─────────────────────────────────────────────────────


def test_provider_aggregation(client: TestClient):
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


def test_regeneration_candidates(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.get(
        "/api/v1/admin/content/quality-regeneration-candidates",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


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

    # Send two reviews from the same admin
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
