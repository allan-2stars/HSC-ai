import io
import json

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy


def _build_csv(content: str) -> io.BytesIO:
    return io.BytesIO(content.encode("utf-8"))


def _build_json(obj: dict | list) -> io.BytesIO:
    return io.BytesIO(json.dumps(obj).encode("utf-8"))


def _upload(client: TestClient, tokens: dict, file_bytes: io.BytesIO, filename: str, skip_duplicates: bool = True) -> dict:
    """Upload a file for preview. Returns the JSON response."""
    resp = client.post(
        "/api/v1/admin/content/import/preview",
        files={"file": (filename, file_bytes, "application/octet-stream")},
        data={"skip_duplicates": str(skip_duplicates).lower()},
        headers=auth_headers(tokens),
    )
    return resp


# ── CSV ──────────────────────────────────────────────────────────────────────


def test_csv_preview_valid_rows(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    csv_content = (
        "question_text,answer,difficulty,subject,exam_type,explanation,source_type\n"
        "What is 2+2?,A,easy,Mathematics,OC,2+2=4,imported\n"
        "What is 8×7?,C,medium,Mathematics,OC,8×7=56,imported\n"
    )
    resp = _upload(client, tokens, _build_csv(csv_content), "test.csv")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 2
    assert data["valid_count"] == 2
    assert data["invalid_count"] == 0


def test_csv_preview_missing_required_fields(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    csv_content = (
        "question_text,answer,subject,exam_type\n"
        "What is 2+2?,,Mathematics,OC\n"  # missing answer
    )
    resp = _upload(client, tokens, _build_csv(csv_content), "test.csv")
    assert resp.status_code == 200
    data = resp.json()
    assert data["invalid_count"] == 1
    assert "Missing required field" in str(data["invalid"][0]["errors"])


def test_csv_preview_unknown_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    csv_content = (
        "question_text,answer,subject,exam_type\n"
        "Test,A,NonexistentSubject,OC\n"
    )
    resp = _upload(client, tokens, _build_csv(csv_content), "test.csv")
    assert resp.status_code == 200
    data = resp.json()
    assert data["invalid_count"] == 1
    assert "Subject not found" in str(data["invalid"][0]["errors"])


def test_csv_import_execute(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    csv_content = (
        "question_text,answer,subject,exam_type,explanation\n"
        "Bulk imported: what is 5+3?,A,Mathematics,OC,5+3=8\n"
    )
    resp = client.post(
        "/api/v1/admin/content/import/execute",
        files={"file": ("test.csv", _build_csv(csv_content), "application/octet-stream")},
        data={"skip_duplicates": "true"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported_count"] == 1
    assert data["status"] == "completed"

    # Verify the question appears in review queue as draft
    resp2 = client.get(
        "/api/v1/admin/content/review?status=draft",
        headers=auth_headers(tokens),
    )
    drafts = resp2.json()
    stems = [q["current_version"]["stem"] for q in drafts if q.get("current_version")]
    assert any("what is 5+3" in s.lower() for s in stems)


# ── JSON ─────────────────────────────────────────────────────────────────────


def test_json_preview(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    obj = {
        "questions": [
            {"question_text": "JSON Q1: 1+1=?", "answer": "B", "subject": "Mathematics", "exam_type": "OC", "explanation": "1+1=2"},
            {"question_text": "JSON Q2: 3-1=?", "answer": "A", "subject": "Mathematics", "exam_type": "OC", "explanation": "3-1=2"},
        ]
    }
    resp = _upload(client, tokens, _build_json(obj), "test.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 2
    assert data["valid_count"] == 2


def test_json_array_format(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    arr = [
        {"question_text": "Array Q1?", "answer": "A", "subject": "Mathematics", "exam_type": "OC"},
    ]
    resp = _upload(client, tokens, _build_json(arr), "test.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == 1


def test_json_nested_array_format(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    arr = [
        {"question_text": "Array Q2?", "answer": "B", "subject": "Mathematics", "exam_type": "OC"},
    ]
    resp = _upload(client, tokens, _build_json(arr), "test.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == 1


# ── Duplicate Detection ──────────────────────────────────────────────────────


def test_duplicate_detection_same_file(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    csv_content = (
        "question_text,answer,subject,exam_type\n"
        "Dup test question,A,Mathematics,OC\n"
        "Dup test question,A,Mathematics,OC\n"
    )
    resp = _upload(client, tokens, _build_csv(csv_content), "test.csv", skip_duplicates=True)
    assert resp.status_code == 200
    data = resp.json()
    assert data["duplicate_count"] == 1
    assert data["valid_count"] == 1


# ── ImportJob ────────────────────────────────────────────────────────────────


def test_import_jobs_list(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    # Execute an import first
    csv_content = (
        "question_text,answer,subject,exam_type\n"
        "Import job test Q,A,Mathematics,OC\n"
    )
    client.post(
        "/api/v1/admin/content/import/execute",
        files={"file": ("test.csv", _build_csv(csv_content), "application/octet-stream")},
        data={"skip_duplicates": "true"},
        headers=auth_headers(tokens),
    )

    resp = client.get(
        "/api/v1/admin/content/import/jobs",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_import_job_detail(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    csv_content = (
        "question_text,answer,subject,exam_type\n"
        "Job detail Q,A,Mathematics,OC\n"
    )
    exec_resp = client.post(
        "/api/v1/admin/content/import/execute",
        files={"file": ("test.csv", _build_csv(csv_content), "application/octet-stream")},
        data={"skip_duplicates": "true"},
        headers=auth_headers(tokens),
    )
    job_id = exec_resp.json()["job_id"]

    resp = client.get(
        f"/api/v1/admin/content/import/jobs/{job_id}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id


# ── Templates ────────────────────────────────────────────────────────────────


def test_can_download_csv_template(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get(
        "/api/v1/admin/content/import/templates/csv",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert "question_text" in resp.text


def test_can_download_json_template(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get(
        "/api/v1/admin/content/import/templates/json",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data


def test_template_list(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get(
        "/api/v1/admin/content/import/templates",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(t["format"] == "csv" for t in data)
    assert any(t["format"] == "xlsx" for t in data)
    assert any(t["format"] == "json" for t in data)


# ── Permissions ──────────────────────────────────────────────────────────────


def test_non_admin_cannot_preview(client: TestClient):
    tokens = register_parent(client)
    csv_content = "question_text,answer,subject,exam_type\nTest,A,Maths,OC\n"
    resp = _upload(client, tokens, _build_csv(csv_content), "test.csv")
    assert resp.status_code == 403


def test_non_admin_cannot_execute(client: TestClient):
    tokens = register_parent(client)
    csv_content = "question_text,answer,subject,exam_type\nTest,A,Maths,OC\n"
    resp = client.post(
        "/api/v1/admin/content/import/execute",
        files={"file": ("test.csv", _build_csv(csv_content), "application/octet-stream")},
        data={"skip_duplicates": "true"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


# ── Outcome Mapping ──────────────────────────────────────────────────────────


def test_outcome_mapping_during_import(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    # Create a curriculum outcome
    from tests.test_curriculum import _create_framework, _create_outcome
    fw = _create_framework(client, tokens, name="Import Test FW")
    outcome = _create_outcome(client, tokens, fw["id"], "IMP-TEST", "Import Test Outcome")

    csv_content = (
        f"question_text,answer,subject,exam_type,curriculum_outcome\n"
        f"Mapped Q,A,Mathematics,OC,IMP-TEST\n"
    )
    exec_resp = client.post(
        "/api/v1/admin/content/import/execute",
        files={"file": ("test.csv", _build_csv(csv_content), "application/octet-stream")},
        data={"skip_duplicates": "true"},
        headers=auth_headers(tokens),
    )
    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["mapping_count"] == 1


# ── Source Type ──────────────────────────────────────────────────────────────


def test_imported_questions_have_source_imported(client: TestClient):
    tokens = create_admin_and_login(client)
    _make_taxonomy(client, tokens)

    csv_content = (
        "question_text,answer,subject,exam_type\n"
        "Source test Q,A,Mathematics,OC\n"
    )
    client.post(
        "/api/v1/admin/content/import/execute",
        files={"file": ("test.csv", _build_csv(csv_content), "application/octet-stream")},
        data={"skip_duplicates": "true"},
        headers=auth_headers(tokens),
    )

    resp = client.get(
        "/api/v1/admin/content/review?source_type=imported",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(q["source_type"] == "imported" for q in data)
    assert all(q["status"] == "draft" for q in data)
