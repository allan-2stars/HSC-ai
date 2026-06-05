import io
import csv
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.user import AdminProfile, User
from app.schemas.import_schema import (
    ImportExecuteRequest,
    ImportJobListResponse,
    ImportPreviewResponse,
    ImportResultResponse,
    TemplateResponse,
)
from app.services import import_service
from app.services.import_service import parse_file, validate_rows

router = APIRouter(prefix="/admin/content", tags=["admin-content-import"])


# ── Preview ──────────────────────────────────────────────────────────────────

@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    skip_duplicates: bool = Form(True),
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await parse_file(file)
    return await validate_rows(rows, db, skip_duplicates=skip_duplicates)


# ── Execute ──────────────────────────────────────────────────────────────────

@router.post("/import/execute", response_model=ImportResultResponse)
async def execute_import(
    file: UploadFile = File(...),
    skip_duplicates: bool = Form(True),
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    rows = await parse_file(file)
    validation = await validate_rows(rows, db, skip_duplicates=skip_duplicates)

    if not validation["valid"]:
        raise HTTPException(status_code=422, detail="No valid rows to import")

    job = await import_service.execute_import(
        valid_rows=validation["valid"],
        admin_id=admin_profile.id,
        filename=file.filename or "unknown",
        file_format=_guess_format(file.filename or ""),
        db=db,
    )
    return {
        "job_id": job.id,
        "filename": job.filename,
        "format": job.format,
        "status": job.status.value,
        "imported_count": job.imported_count,
        "skipped_count": job.skipped_count,
        "failed_count": job.failed_count,
        "duplicate_count": job.duplicate_count,
        "mapping_count": job.mapping_count,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
    }


# ── Jobs ─────────────────────────────────────────────────────────────────────

@router.get("/import/jobs", response_model=list[ImportJobListResponse])
async def list_import_jobs(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await import_service.list_import_jobs(db)


@router.get("/import/jobs/{job_id}", response_model=ImportResultResponse)
async def get_import_job(
    job_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    job = await import_service.get_import_job(job_id, db)
    return {
        "job_id": job.id,
        "filename": job.filename,
        "format": job.format,
        "status": job.status.value,
        "imported_count": job.imported_count,
        "skipped_count": job.skipped_count,
        "failed_count": job.failed_count,
        "duplicate_count": job.duplicate_count,
        "mapping_count": job.mapping_count,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
    }


# ── Templates ────────────────────────────────────────────────────────────────

def _guess_format(filename: str) -> str:
    fn = filename.lower()
    if fn.endswith(".xlsx"):
        return "xlsx"
    if fn.endswith(".json"):
        return "json"
    return "csv"


_CSV_TEMPLATE_HEADERS = [
    "question_text", "answer", "difficulty", "subject", "exam_type",
    "explanation", "topic", "skill", "curriculum_outcome", "source_type",
]

_CSV_SAMPLE = [
    ["What is 2 + 2?", "A", "easy", "Mathematics", "OC",
     "2 + 2 = 4 because addition combines values.", "Number & Algebra",
     "Addition/Subtraction", "OC-MATH-NUM", "imported"],
    ["What is 8 × 7?", "C", "medium", "Mathematics", "OC",
     "8 × 7 = 56.", "Number & Algebra", "Multiplication/Division", "OC-MATH-NUM", "imported"],
]


@router.get("/import/templates/{fmt}")
async def download_template(fmt: str):
    fmt = fmt.lower()
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(_CSV_TEMPLATE_HEADERS)
        for row in _CSV_SAMPLE:
            writer.writerow(row)
        content = output.getvalue()
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=import_template.csv"},
        )
    elif fmt == "json":
        obj = {"questions": [dict(zip(_CSV_TEMPLATE_HEADERS, r)) for r in _CSV_SAMPLE]}
        return Response(
            content=json.dumps(obj, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=import_template.json"},
        )
    elif fmt == "xlsx":
        try:
            from openpyxl import Workbook
        except ImportError:
            raise HTTPException(status_code=500, detail="Excel support not installed")

        wb = Workbook()
        ws = wb.active
        ws.append(_CSV_TEMPLATE_HEADERS)
        for row in _CSV_SAMPLE:
            ws.append(row)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=import_template.xlsx"},
        )
    else:
        raise HTTPException(status_code=422, detail="Unknown format. Use csv, xlsx, or json.")


@router.get("/import/templates", response_model=list[TemplateResponse])
async def list_templates():
    return [
        {"format": "csv", "download_url": "/api/v1/admin/content/import/templates/csv", "description": "CSV template with sample data"},
        {"format": "xlsx", "download_url": "/api/v1/admin/content/import/templates/xlsx", "description": "Excel template with sample data"},
        {"format": "json", "download_url": "/api/v1/admin/content/import/templates/json", "description": "JSON template with sample data"},
    ]
