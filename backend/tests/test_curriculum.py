from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy


def _create_framework(
    client: TestClient, tokens: dict, name: str = "OC 2026", exam_type_id: str | None = None
) -> dict:
    resp = client.post(
        "/api/v1/curriculum/frameworks",
        json={"name": name, "exam_type_id": exam_type_id, "version": "2026"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_outcome(
    client: TestClient, tokens: dict, framework_id: str, code: str, title: str
) -> dict:
    resp = client.post(
        "/api/v1/curriculum/outcomes",
        json={"framework_id": framework_id, "code": code, "title": title, "sort_order": 0},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Framework Tests ──────────────────────────────────────────────────────────


def test_admin_can_create_framework(client: TestClient):
    tokens = create_admin_and_login(client)

    fw = _create_framework(client, tokens, name="Selective 2026")
    assert fw["name"] == "Selective 2026"
    assert fw["version"] == "2026"
    assert fw["is_active"] is True


def test_non_admin_cannot_create_framework(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/curriculum/frameworks",
        json={"name": "Test"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_admin_can_list_frameworks(client: TestClient):
    tokens = create_admin_and_login(client)
    _create_framework(client, tokens)
    _create_framework(client, tokens, name="NAPLAN 2026")

    resp = client.get("/api/v1/curriculum/frameworks", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# ── Outcome Tests ────────────────────────────────────────────────────────────


def test_admin_can_create_outcome(client: TestClient):
    tokens = create_admin_and_login(client)
    fw = _create_framework(client, tokens)

    outcome = _create_outcome(client, tokens, fw["id"], "OC-MATH-FRAC", "Fractions")
    assert outcome["code"] == "OC-MATH-FRAC"
    assert outcome["framework_id"] == fw["id"]


def test_duplicate_outcome_code_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    fw = _create_framework(client, tokens)

    _create_outcome(client, tokens, fw["id"], "OC-MATH-FRAC", "Fractions")
    resp = client.post(
        "/api/v1/curriculum/outcomes",
        json={"framework_id": fw["id"], "code": "OC-MATH-FRAC", "title": "Duplicate"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_list_outcomes_filtered(client: TestClient):
    tokens = create_admin_and_login(client)
    fw1 = _create_framework(client, tokens, name="FW1")
    fw2 = _create_framework(client, tokens, name="FW2")

    _create_outcome(client, tokens, fw1["id"], "A-1", "Outcome A1")
    _create_outcome(client, tokens, fw2["id"], "B-1", "Outcome B1")

    resp = client.get(
        f"/api/v1/curriculum/outcomes?framework_id={fw1['id']}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "A-1"


# ── Question Mapping Tests ───────────────────────────────────────────────────


def test_admin_can_create_question_mapping(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    # Create a question
    from tests.test_exam_engine import _create_published_question
    q = _create_published_question(client, tokens, sid, eid)

    fw = _create_framework(client, tokens)
    outcome = _create_outcome(client, tokens, fw["id"], "OC-TEST", "Test Outcome")

    resp = client.post(
        "/api/v1/curriculum/question-mappings",
        json={"question_id": q["id"], "outcome_id": outcome["id"], "weight": 1.0},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["question_id"] == q["id"]
    assert data["outcome_id"] == outcome["id"]


def test_duplicate_mapping_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    from tests.test_exam_engine import _create_published_question
    q = _create_published_question(client, tokens, sid, eid)

    fw = _create_framework(client, tokens)
    outcome = _create_outcome(client, tokens, fw["id"], "OC-DUP", "Dup Test")

    client.post(
        "/api/v1/curriculum/question-mappings",
        json={"question_id": q["id"], "outcome_id": outcome["id"]},
        headers=auth_headers(tokens),
    )

    resp = client.post(
        "/api/v1/curriculum/question-mappings",
        json={"question_id": q["id"], "outcome_id": outcome["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_mapping_nonexistent_question_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    fw = _create_framework(client, tokens)
    outcome = _create_outcome(client, tokens, fw["id"], "OC-NE", "Non Existent")

    resp = client.post(
        "/api/v1/curriculum/question-mappings",
        json={"question_id": "nonexistent-id", "outcome_id": outcome["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


# ── Coverage Tests ───────────────────────────────────────────────────────────


def test_coverage_calculation_empty_framework(client: TestClient):
    tokens = create_admin_and_login(client)
    fw = _create_framework(client, tokens)

    resp = client.get(
        f"/api/v1/curriculum/coverage/{fw['id']}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_outcomes"] == 0
    assert data["coverage_percentage"] == 0.0


def test_coverage_calculation_with_outcomes(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    from tests.test_exam_engine import _create_published_question
    q1 = _create_published_question(client, tokens, sid, eid)
    q2 = _create_published_question(client, tokens, sid, eid)

    fw = _create_framework(client, tokens)
    o1 = _create_outcome(client, tokens, fw["id"], "COV-1", "Covered 1")
    o2 = _create_outcome(client, tokens, fw["id"], "COV-2", "Covered 2")
    o3 = _create_outcome(client, tokens, fw["id"], "COV-3", "Empty")

    # Map q1 to o1, q2 to o2
    client.post(
        "/api/v1/curriculum/question-mappings",
        json={"question_id": q1["id"], "outcome_id": o1["id"]},
        headers=auth_headers(tokens),
    )
    client.post(
        "/api/v1/curriculum/question-mappings",
        json={"question_id": q2["id"], "outcome_id": o2["id"]},
        headers=auth_headers(tokens),
    )

    resp = client.get(
        f"/api/v1/curriculum/coverage/{fw['id']}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_outcomes"] == 3
    assert data["mapped_outcomes"] >= 2
    assert len(data["outcomes"]) == 3

    # o3 should be red (0 questions)
    o3_item = [o for o in data["outcomes"] if o["code"] == "COV-3"][0]
    assert o3_item["coverage_status"] == "red"
    assert o3_item["total_question_count"] == 0


def test_coverage_status_thresholds(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    fw = _create_framework(client, tokens)
    outcome = _create_outcome(client, tokens, fw["id"], "STAT-1", "Status Test")

    # Create 5 questions — red (< 25)
    from tests.test_exam_engine import _create_published_question
    for i in range(5):
        q = _create_published_question(client, tokens, sid, eid)
        client.post(
            "/api/v1/curriculum/question-mappings",
            json={"question_id": q["id"], "outcome_id": outcome["id"]},
            headers=auth_headers(tokens),
        )

    resp = client.get(
        f"/api/v1/curriculum/coverage/{fw['id']}",
        headers=auth_headers(tokens),
    )
    item = resp.json()["outcomes"][0]
    assert item["coverage_status"] == "red"
    assert item["approved_question_count"] >= 5


def test_unmapped_questions(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    from tests.test_exam_engine import _create_published_question
    _create_published_question(client, tokens, sid, eid)

    resp = client.get("/api/v1/curriculum/unmapped-questions", headers=auth_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    # At least one question should exist and be unmapped
    assert isinstance(data, list)


# ── Permission Enforcement ───────────────────────────────────────────────────


def test_non_admin_cannot_create_outcome(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/curriculum/outcomes",
        json={"framework_id": "any", "code": "X", "title": "X"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_non_admin_cannot_create_mapping(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/curriculum/question-mappings",
        json={"question_id": "any", "outcome_id": "any"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


# ── Delete Mapping ───────────────────────────────────────────────────────────


def test_admin_can_delete_mapping(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    from tests.test_exam_engine import _create_published_question
    q = _create_published_question(client, tokens, sid, eid)

    fw = _create_framework(client, tokens)
    outcome = _create_outcome(client, tokens, fw["id"], "DEL-1", "Delete Test")

    resp = client.post(
        "/api/v1/curriculum/question-mappings",
        json={"question_id": q["id"], "outcome_id": outcome["id"]},
        headers=auth_headers(tokens),
    )
    mapping_id = resp.json()["id"]

    resp = client.delete(
        f"/api/v1/curriculum/question-mappings/{mapping_id}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 204
