from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.user import AdminProfile, User
from app.schemas.ai_schema import (
    AIGenerationExecuteResponse,
    AIGenerationPreviewResponse,
    AIGenerationRequest,
    AIJobDetailResponse,
    AIJobListResponse,
)
from app.services import ai_service

router = APIRouter(prefix="/admin/content", tags=["admin-ai-generate"])


# ── Preview ──────────────────────────────────────────────────────────────────

@router.post("/ai-generate/preview", response_model=AIGenerationPreviewResponse)
async def preview_ai_generation(
    body: AIGenerationRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ai_service.preview_generation(
        outcome_id=body.outcome_id,
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
        count=body.count,
        difficulty_mix=body.difficulty_mix or {"easy": 33, "medium": 34, "hard": 33},
        provider_name=body.provider,
        db=db,
    )


# ── Execute ──────────────────────────────────────────────────────────────────

@router.post("/ai-generate/execute", response_model=AIGenerationExecuteResponse)
async def execute_ai_generation(
    body: AIGenerationRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    job = await ai_service.execute_generation(
        params={
            "outcome_id": body.outcome_id,
            "framework_id": body.framework_id,
            "subject_id": body.subject_id,
            "exam_type_id": body.exam_type_id,
            "count": body.count,
            "difficulty_mix": body.difficulty_mix or {"easy": 33, "medium": 34, "hard": 33},
            "provider": body.provider,
        },
        admin_id=admin_profile.id,
        db=db,
    )
    return {
        "job_id": job.id,
        "provider": job.provider,
        "requested_count": job.requested_count,
        "generated_count": job.generated_count,
        "saved_count": job.saved_count,
        "rejected_count": job.rejected_count,
        "status": job.status.value,
        "estimated_cost": job.estimated_cost,
        "completed_at": job.completed_at,
    }


# ── Jobs ─────────────────────────────────────────────────────────────────────

@router.get("/ai-generate/jobs", response_model=list[AIJobListResponse])
async def list_ai_jobs(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    jobs = await ai_service.list_ai_jobs(db)
    return [
        {
            "id": j.id,
            "provider": j.provider,
            "outcome_id": j.outcome_id,
            "subject_id": j.subject_id,
            "exam_type_id": j.exam_type_id,
            "requested_count": j.requested_count,
            "saved_count": j.saved_count,
            "status": j.status.value,
            "created_at": j.created_at,
        }
        for j in jobs
    ]


@router.get("/ai-generate/jobs/{job_id}", response_model=AIJobDetailResponse)
async def get_ai_job(
    job_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    job = await ai_service.get_ai_job(job_id, db)
    return {
        "id": job.id,
        "provider": job.provider,
        "framework_id": job.framework_id,
        "outcome_id": job.outcome_id,
        "subject_id": job.subject_id,
        "exam_type_id": job.exam_type_id,
        "requested_count": job.requested_count,
        "generated_count": job.generated_count,
        "saved_count": job.saved_count,
        "rejected_count": job.rejected_count,
        "status": job.status.value,
        "error_message": job.error_message,
        "token_usage_json": job.token_usage_json,
        "estimated_cost": job.estimated_cost,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }
