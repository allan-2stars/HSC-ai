from fastapi.testclient import TestClient

from tests.conftest import auth_headers, create_admin_and_login, register_parent


def _make_taxonomy(client: TestClient, tokens: dict) -> tuple[str, str]:
    subj = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    ).json()
    et = client.post(
        "/api/v1/admin/exam-types",
        json={"code": "oc", "name": "Opportunity Class"},
        headers=auth_headers(tokens),
    ).json()
    return subj["id"], et["id"]


def _make_question_payload(subject_id: str, exam_type_id: str) -> dict:
    return {
        "subject_id": subject_id,
        "exam_type_id": exam_type_id,
        "year_level": 5,
        "difficulty": "medium",
        "question_type": "mcq",
        "source_type": "manual",
        "content_ownership": "original",
        "stem": "What is 2 + 2?",
        "correct_answer": "A",
        "full_explanation": "2 + 2 = 4, which is option A.",
        "marks": 1,
        "options_json": [
            {"label": "A", "text": "4", "is_correct": True, "explanation": "Correct"},
            {"label": "B", "text": "3", "is_correct": False, "explanation": "Too low"},
            {"label": "C", "text": "5", "is_correct": False, "explanation": "Too high"},
            {"label": "D", "text": "6", "is_correct": False, "explanation": "Too high"},
        ],
    }


def test_admin_can_create_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    resp = client.post(
        "/api/v1/admin/questions",
        json=_make_question_payload(sid, eid),
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["current_version"]["version_number"] == 1
    assert data["current_version"]["stem"] == "What is 2 + 2?"
    assert data["year_level"] == 5


def test_non_admin_cannot_create_question(client: TestClient):
    tokens = register_parent(client)
    resp = client.post("/api/v1/admin/questions", json={}, headers=auth_headers(tokens))
    assert resp.status_code == 403


def test_question_starts_as_draft(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    resp = client.post(
        "/api/v1/admin/questions",
        json=_make_question_payload(sid, eid),
        headers=auth_headers(tokens),
    )
    assert resp.json()["status"] == "draft"


def test_admin_can_list_questions(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens))
    client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/questions", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_can_filter_questions_by_status(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens))
    draft_resp = client.get("/api/v1/admin/questions?status=draft", headers=auth_headers(tokens))
    assert len(draft_resp.json()) == 1
    review_resp = client.get("/api/v1/admin/questions?status=review", headers=auth_headers(tokens))
    assert len(review_resp.json()) == 1


def test_admin_can_get_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    created = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.get(f"/api/v1/admin/questions/{created['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_nonexistent_question_returns_404(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/questions/nonexistent-id", headers=auth_headers(tokens))
    assert resp.status_code == 404


def test_status_transition_draft_to_review(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "review"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "review"


def test_status_transition_review_to_approved(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "approved"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_can_publish_original_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "approved"}, headers=auth_headers(tokens))
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


def test_cannot_publish_internal_draft_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    payload = _make_question_payload(sid, eid)
    payload["content_ownership"] = "internal_draft"
    q = client.post("/api/v1/admin/questions", json=payload, headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "approved"}, headers=auth_headers(tokens))
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_cannot_publish_restricted_reference_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    payload = _make_question_payload(sid, eid)
    payload["content_ownership"] = "restricted_reference_only"
    q = client.post("/api/v1/admin/questions", json=payload, headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "approved"}, headers=auth_headers(tokens))
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_invalid_status_transition_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


def test_admin_can_add_new_version(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.post(
        f"/api/v1/admin/questions/{q['id']}/versions",
        json={
            "stem": "What is 3 + 3?",
            "correct_answer": "B",
            "full_explanation": "3 + 3 = 6, which is option B.",
            "marks": 1,
            "options_json": [
                {"label": "A", "text": "5", "is_correct": False, "explanation": "Wrong"},
                {"label": "B", "text": "6", "is_correct": True, "explanation": "Correct"},
            ],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["version_number"] == 2
    assert resp.json()["stem"] == "What is 3 + 3?"


def test_new_version_updates_current_version_on_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    assert q["current_version"]["version_number"] == 1
    client.post(
        f"/api/v1/admin/questions/{q['id']}/versions",
        json={"stem": "Updated stem.", "full_explanation": "Updated explanation.", "marks": 1},
        headers=auth_headers(tokens),
    )
    updated = client.get(f"/api/v1/admin/questions/{q['id']}", headers=auth_headers(tokens)).json()
    assert updated["current_version"]["version_number"] == 2


def test_admin_can_list_versions(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.post(
        f"/api/v1/admin/questions/{q['id']}/versions",
        json={"stem": "V2 stem.", "full_explanation": "V2 explanation.", "marks": 1},
        headers=auth_headers(tokens),
    )
    resp = client.get(f"/api/v1/admin/questions/{q['id']}/versions", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.json()[0]["version_number"] == 1
    assert resp.json()[1]["version_number"] == 2
