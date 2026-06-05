from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.question import QuestionStatus, SourceType
from app.models.user import AdminProfile, User
from app.schemas.question import (
    BulkActionRequest,
    ContentStatsResponse,
    QuestionResponse,
    SubmitReviewRequest,
)
from app.services import question_service

router = APIRouter(prefix="/admin/content", tags=["admin-content-review"])


# ── Review Queue ─────────────────────────────────────────────────────────────

@router.get("/review", response_model=list[QuestionResponse])
async def list_review_queue(
    status: QuestionStatus | None = None,
    subject_id: str | None = None,
    exam_type_id: str | None = None,
    source_type: SourceType | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_review_queue(
        db=db,
        status_filter=status,
        subject_id=subject_id,
        exam_type_id=exam_type_id,
        source_type=source_type,
    )


# ── Individual Actions ───────────────────────────────────────────────────────

@router.post("/questions/{question_id}/submit-review", response_model=QuestionResponse)
async def submit_for_review(
    question_id: str,
    body: SubmitReviewRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.submit_for_review(
        question_id=question_id,
        admin_id=admin_profile.id,
        db=db,
        quality_score=body.quality_score,
        review_notes=body.review_notes,
    )


@router.post("/questions/{question_id}/approve", response_model=QuestionResponse)
async def approve_question(
    question_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.approve_question(
        question_id=question_id,
        admin_id=admin_profile.id,
        db=db,
    )


@router.post("/questions/{question_id}/publish", response_model=QuestionResponse)
async def publish_question(
    question_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.publish_question(
        question_id=question_id,
        db=db,
    )


@router.post("/questions/{question_id}/archive", response_model=QuestionResponse)
async def archive_question(
    question_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.archive_question(
        question_id=question_id,
        db=db,
    )


# ── Bulk Actions ─────────────────────────────────────────────────────────────

@router.post("/bulk-action")
async def bulk_action(
    body: BulkActionRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    count = await question_service.bulk_action(
        question_ids=body.question_ids,
        action=body.action,
        admin_id=admin_profile.id,
        db=db,
    )
    return {"action": body.action, "affected": count}


# ── Content Stats ────────────────────────────────────────────────────────────

@router.get("/stats", response_model=ContentStatsResponse)
async def content_stats(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.get_content_stats(db)
