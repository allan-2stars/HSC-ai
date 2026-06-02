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
        "full_explanation": "2 + 2 = 4.",
        "marks": 1,
    }


def test_admin_can_create_pool(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/pools",
        json={"name": "Year 5 OC Maths"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Year 5 OC Maths"
    assert data["pool_type"] == "static"


def test_non_admin_cannot_create_pool(client: TestClient):
    tokens = register_parent(client)
    resp = client.post("/api/v1/admin/pools", json={"name": "Pool"}, headers=auth_headers(tokens))
    assert resp.status_code == 403


def test_admin_can_list_pools(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/pools", json={"name": "Pool A"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/pools", json={"name": "Pool B"}, headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/pools", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_admin_can_get_pool(client: TestClient):
    tokens = create_admin_and_login(client)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool A"}, headers=auth_headers(tokens)).json()
    resp = client.get(f"/api/v1/admin/pools/{pool['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["id"] == pool["id"]


def test_admin_can_add_question_to_pool(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.post(
        f"/api/v1/admin/pools/{pool['id']}/members",
        json={"question_id": q["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201


def test_admin_can_list_pool_members(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.post(f"/api/v1/admin/pools/{pool['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    resp = client.get(f"/api/v1/admin/pools/{pool['id']}/members", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == q["id"]


def test_duplicate_pool_membership_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.post(f"/api/v1/admin/pools/{pool['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    resp = client.post(
        f"/api/v1/admin/pools/{pool['id']}/members",
        json={"question_id": q["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_admin_can_remove_question_from_pool(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.post(f"/api/v1/admin/pools/{pool['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    resp = client.delete(
        f"/api/v1/admin/pools/{pool['id']}/members/{q['id']}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 204
    members = client.get(f"/api/v1/admin/pools/{pool['id']}/members", headers=auth_headers(tokens)).json()
    assert len(members) == 0


def test_remove_nonexistent_member_returns_404(client: TestClient):
    tokens = create_admin_and_login(client)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    resp = client.delete(
        f"/api/v1/admin/pools/{pool['id']}/members/nonexistent-id",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


def test_add_to_nonexistent_pool_returns_404(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.post(
        "/api/v1/admin/pools/nonexistent-pool/members",
        json={"question_id": q["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


def test_add_nonexistent_question_to_pool_returns_404(client: TestClient):
    tokens = create_admin_and_login(client)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    resp = client.post(
        f"/api/v1/admin/pools/{pool['id']}/members",
        json={"question_id": "nonexistent-question"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


def test_question_can_be_in_multiple_pools(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool_a = client.post("/api/v1/admin/pools", json={"name": "Pool A"}, headers=auth_headers(tokens)).json()
    pool_b = client.post("/api/v1/admin/pools", json={"name": "Pool B"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    r1 = client.post(f"/api/v1/admin/pools/{pool_a['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    r2 = client.post(f"/api/v1/admin/pools/{pool_b['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    assert r1.status_code == 201
    assert r2.status_code == 201
