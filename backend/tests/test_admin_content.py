from fastapi.testclient import TestClient

from tests.conftest import auth_headers, create_admin_and_login, register_parent


def test_admin_can_create_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "maths"
    assert data["name"] == "Mathematics"
    assert data["is_active"] is True
    assert "id" in data


def test_non_admin_cannot_create_subject(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_unauthenticated_cannot_create_subject(client: TestClient):
    resp = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"})
    assert resp.status_code == 401


def test_duplicate_subject_code_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    )
    resp = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Maths Duplicate"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_admin_can_list_subjects(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Mathematics"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/subjects", json={"code": "english", "name": "English"}, headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/subjects", headers=auth_headers(tokens))
    assert resp.status_code == 200
    codes = {s["code"] for s in resp.json()}
    assert codes == {"maths", "english"}


def test_admin_can_get_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    created = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    resp = client.get(f"/api/v1/admin/subjects/{created['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_admin_can_update_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    created = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    resp = client.patch(
        f"/api/v1/admin/subjects/{created['id']}",
        json={"name": "Mathematics Updated"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Mathematics Updated"


def test_admin_can_create_exam_type(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/exam-types",
        json={"code": "oc", "name": "Opportunity Class"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "oc"


def test_duplicate_exam_type_code_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/exam-types", json={"code": "oc", "name": "OC"}, headers=auth_headers(tokens))
    resp = client.post("/api/v1/admin/exam-types", json={"code": "oc", "name": "OC2"}, headers=auth_headers(tokens))
    assert resp.status_code == 409


def test_admin_can_list_exam_types(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/exam-types", json={"code": "oc", "name": "OC"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/exam-types", json={"code": "selective", "name": "Selective"}, headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/exam-types", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_admin_can_create_topic(client: TestClient):
    tokens = create_admin_and_login(client)
    subj = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    resp = client.post(
        "/api/v1/admin/topics",
        json={"subject_id": subj["id"], "name": "Fractions"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Fractions"
    assert resp.json()["subject_id"] == subj["id"]


def test_topic_requires_valid_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/topics",
        json={"subject_id": "nonexistent-id", "name": "Fractions"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


def test_admin_can_list_topics_by_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    subj = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    client.post("/api/v1/admin/topics", json={"subject_id": subj["id"], "name": "Fractions"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/topics", json={"subject_id": subj["id"], "name": "Decimals"}, headers=auth_headers(tokens))
    resp = client.get(f"/api/v1/admin/topics?subject_id={subj['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_admin_can_create_skill_tag(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/skill-tags",
        json={"name": "Pattern Recognition"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Pattern Recognition"
    assert resp.json()["subject_id"] is None


def test_admin_can_create_skill_tag_with_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    subj = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    resp = client.post(
        "/api/v1/admin/skill-tags",
        json={"name": "Arithmetic", "subject_id": subj["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["subject_id"] == subj["id"]


def test_admin_can_list_skill_tags(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/skill-tags", json={"name": "Tag A"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/skill-tags", json={"name": "Tag B"}, headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/skill-tags", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2
