from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.user import AdminProfile, User
from app.schemas.ocr_schema import (
    OCRBulkResultResponse,
    OCRCreateDraftsRequest,
    OCRJobListResponse,
    OCRJobResponse,
)
from app.services import ocr_service

router = APIRouter(prefix="/admin/content", tags=["admin-content-ocr"])


def _job_to_response(job) -> dict:
    results = job.ocr_results_json or {}
    return {
        "id": job.id,
        "filename": job.filename,
        "file_format": job.file_format,
        "status": job.status.value,
        "questions_detected": job.questions_detected,
        "questions_created": job.questions_created,
        "raw_text": results.get("raw_text", ""),
        "pages": results.get("pages", []),
        "questions": results.get("questions", []),
        "error_message": job.error_message,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
    }


# ── Upload + Extract ─────────────────────────────────────────────────────────

@router.post("/ocr/upload", response_model=OCRJobResponse)
async def upload_ocr_file(
    file: UploadFile = File(...),
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    filename = (file.filename or "unknown").lower()
    file_format = "png"
    for ext in ("pdf", "png", "jpg", "jpeg", "webp"):
        if filename.endswith(ext):
            file_format = ext
            break

    # Extract text
    full_text, pages = await ocr_service.extract_text(file)

    # Create job
    job = await ocr_service.create_ocr_job(admin_profile.id, file.filename or "unknown", file_format, db)

    # Store extraction results
    job.ocr_results_json = {"raw_text": full_text, "pages": pages}
    await db.commit()

    # Process (detect questions)
    job = await ocr_service.process_ocr_job(job.id, db)

    return _job_to_response(job)


# ── Bulk Upload ──────────────────────────────────────────────────────────────

@router.post("/ocr/upload-bulk", response_model=OCRBulkResultResponse)
async def upload_ocr_files_bulk(
    files: list[UploadFile] = File(...),
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple files. All share a single OCR job."""
    if not files:
        raise HTTPException(status_code=422, detail="No files provided")

    # Extract text from all files
    all_text = []
    all_pages = []
    page_offset = 0

    for f in files:
        filename = (f.filename or "unknown").lower()
        file_format = "png"
        for ext in ("pdf", "png", "jpg", "jpeg", "webp"):
            if filename.endswith(ext):
                file_format = ext
                break

        full_text, pages = await ocr_service.extract_text(f)
        all_text.append(full_text)

        # Re-number pages across files
        for p in pages:
            p["page_number"] += page_offset
        all_pages.extend(pages)
        page_offset += len(pages)

    combined_text = "\n\n".join(all_text)
    combined_filename = f"{files[0].filename}_plus_{len(files)-1}_more" if len(files) > 1 else (files[0].filename or "unknown")

    # Create one job for all files
    file_ext = (files[0].filename or "").lower()
    job_format = "pdf" if file_ext.endswith(".pdf") else "png"
    job = await ocr_service.create_ocr_job(admin_profile.id, combined_filename, job_format, db)
    job.ocr_results_json = {"raw_text": combined_text, "pages": all_pages}
    await db.commit()
    job = await ocr_service.process_ocr_job(job.id, db)

    return {
        "job_ids": [job.id],
        "total_files": len(files),
        "total_pages": len(all_pages),
        "total_questions": job.questions_detected,
        "jobs": [_job_to_response(job)],
    }


# ── Reprocess ────────────────────────────────────────────────────────────────

@router.post("/ocr/{job_id}/process", response_model=OCRJobResponse)
async def process_ocr_job(
    job_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    job = await ocr_service.process_ocr_job(job_id, db)
    return _job_to_response(job)


# ── Create Drafts ────────────────────────────────────────────────────────────

@router.post("/ocr/{job_id}/create-drafts", response_model=OCRJobResponse)
async def create_ocr_drafts(
    job_id: str,
    body: OCRCreateDraftsRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    job = await ocr_service.create_drafts_from_ocr(
        job_id=job_id,
        admin_id=admin_profile.id,
        db=db,
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
    )
    return _job_to_response(job)


# ── Jobs ─────────────────────────────────────────────────────────────────────

@router.get("/ocr/jobs", response_model=list[OCRJobListResponse])
async def list_ocr_jobs(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    jobs = await ocr_service.list_ocr_jobs(db)
    return [
        {
            "id": j.id,
            "filename": j.filename,
            "file_format": j.file_format,
            "status": j.status.value,
            "questions_detected": j.questions_detected,
            "questions_created": j.questions_created,
            "created_at": j.created_at,
        }
        for j in jobs
    ]


@router.get("/ocr/jobs/{job_id}", response_model=OCRJobResponse)
async def get_ocr_job(
    job_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    job = await ocr_service.get_ocr_job(job_id, db)
    return _job_to_response(job)
