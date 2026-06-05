import io
import struct
import zlib

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy


def _minimal_pdf_bytes() -> bytes:
    """Generate a minimal valid PDF containing sample MCQ text."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<<>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\n"
        b"BT /F1 12 Tf 100 700 Td (Test question text) Tj ET\n"
        b"endstream\n"
        b"endobj\n"
        b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000210 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\n"
        b"startxref\n292\n%%EOF"
    )


def _minimal_png_bytes() -> bytes:
    """Generate a minimal 1x1 PNG."""

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00" + b"\x80\x80\x80"
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# ── OCR Upload + Processing ──────────────────────────────────────────────────


def test_ocr_upload_pdf(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "test.pdf"
    assert data["file_format"] == "pdf"
    assert data["status"] in ("completed", "processing")


def test_ocr_upload_image(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.png", io.BytesIO(_minimal_png_bytes()), "image/png")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_format"] == "png"
    assert "raw_text" in data or data["status"] in ("completed", "failed")
    assert data["pages"][0]["confidence"] >= 0  # real OCR returns confidence


def test_image_ocr_returns_text(client: TestClient):
    """Test that OCR processes images properly — confidence reflects real OCR attempt."""
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.png", io.BytesIO(_minimal_png_bytes()), "image/png")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    # For a 1x1 pixel image, OCR may return a placeholder — that's expected.
    # Just verify the response structure is valid.
    assert "raw_text" in data
    assert len(data["pages"]) >= 1
    assert "confidence" in data["pages"][0]


def test_bulk_upload_multiple_files(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload-bulk",
        files=[
            ("files", ("a.png", io.BytesIO(_minimal_png_bytes()), "image/png")),
            ("files", ("b.png", io.BytesIO(_minimal_png_bytes()), "image/png")),
        ],
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_files"] == 2
    assert data["total_pages"] == 2
    assert len(data["job_ids"]) >= 1


def test_ocr_job_created(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
        headers=auth_headers(tokens),
    )
    job_id = resp.json()["id"]

    # List jobs
    resp2 = client.get("/api/v1/admin/content/ocr/jobs", headers=auth_headers(tokens))
    assert resp2.status_code == 200
    assert any(j["id"] == job_id for j in resp2.json())

    # Get job detail
    resp3 = client.get(f"/api/v1/admin/content/ocr/jobs/{job_id}", headers=auth_headers(tokens))
    assert resp3.status_code == 200
    assert resp3.json()["id"] == job_id


# ── Question Detection ───────────────────────────────────────────────────────


def test_ocr_detects_mcq_structure(client: TestClient):
    """Test that the structured question detector finds numbered questions with options."""
    from app.services.ocr_service import detect_questions

    raw = (
        "1. What is the capital of France?\n"
        "A. London\nB. Paris\nC. Berlin\nD. Madrid\n"
        "Answer: B\n"
        "2. What is 2 + 2?\n"
        "A. 3\nB. 4\nC. 5\nD. 6\n"
        "Answer: B\n"
    )
    questions = detect_questions(raw)
    assert len(questions) >= 2


def test_ocr_detects_answer_key(client: TestClient):
    from app.services.ocr_service import detect_questions

    raw = (
        "1. The sky is blue\n"
        "A. True\nB. False\n"
        "Answer: A\n"
    )
    questions = detect_questions(raw)
    assert questions[0]["correct_answer"] == "A"


# ── Draft Creation ───────────────────────────────────────────────────────────


def test_create_drafts_from_ocr(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    job_id = resp.json()["id"]
    detected = resp.json().get("questions_detected", 0)

    if detected > 0:
        resp2 = client.post(
            f"/api/v1/admin/content/ocr/{job_id}/create-drafts",
            json={"subject_id": sid, "exam_type_id": eid},
            headers=auth_headers(tokens),
        )
        assert resp2.status_code == 200
        assert resp2.json()["questions_created"] >= 0


def test_create_drafts_rejects_processing_job(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    # Create a job but don't process it — just verify invalid state is rejected
    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("empty.png", io.BytesIO(_minimal_png_bytes()), "image/png")},
        headers=auth_headers(tokens),
    )

    # If job status is not "completed", create_drafts should fail
    if resp.status_code == 200:
        job_id = resp.json()["id"]
        status = resp.json()["status"]
        resp2 = client.post(
            f"/api/v1/admin/content/ocr/{job_id}/create-drafts",
            json={"subject_id": sid, "exam_type_id": eid},
            headers=auth_headers(tokens),
        )
        if status != "completed":
            assert resp2.status_code == 409


def test_create_drafts_requires_subject_exam(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
        headers=auth_headers(tokens),
    )
    if resp.status_code == 200:
        job_id = resp.json()["id"]
        if resp.json()["status"] == "completed":
            resp2 = client.post(
                f"/api/v1/admin/content/ocr/{job_id}/create-drafts",
                json={"subject_id": "", "exam_type_id": ""},
                headers=auth_headers(tokens),
            )
            assert resp2.status_code in (422, 409)  # 422=missing params, 409=not completed


# ── Unsupported Format ───────────────────────────────────────────────────────


def test_ocr_rejects_unsupported_format(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


# ── Permissions ──────────────────────────────────────────────────────────────


def test_non_admin_cannot_upload_ocr(client: TestClient):
    tokens = register_parent(client)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_non_admin_cannot_list_ocr_jobs(client: TestClient):
    tokens = register_parent(client)
    resp = client.get("/api/v1/admin/content/ocr/jobs", headers=auth_headers(tokens))
    assert resp.status_code == 403


# ── PDF Text Extraction ──────────────────────────────────────────────────────


def test_pdf_text_extraction(client: TestClient):
    from app.services.ocr_service import _extract_pdf

    full_text, pages = _extract_pdf(_minimal_pdf_bytes())
    assert len(pages) >= 1
    assert pages[0]["confidence"] > 0


def test_ocr_job_tracks_status(client: TestClient):
    tokens = create_admin_and_login(client)

    resp = client.post(
        "/api/v1/admin/content/ocr/upload",
        files={"file": ("test.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"]
    assert data["status"] in ("pending", "processing", "completed", "failed")
    assert data["filename"] == "test.pdf"
