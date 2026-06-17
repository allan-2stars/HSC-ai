from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin_profile
from app.models.user import AdminProfile
from app.models.writing import WritingTaskStatus
from app.schemas.writing_schema import (
    WritingFeedbackCreate,
    WritingSubmissionListItem,
    WritingTaskCreate,
    WritingTaskResponse,
)
from app.services import writing_review_service, writing_service

router = APIRouter(prefix="/admin/writing", tags=["admin-writing"])


# ── Tasks ──────────────────────────────────────────────────────────────────


@router.post("/tasks", response_model=WritingTaskResponse, status_code=201)
async def create_writing_task(
    body: WritingTaskCreate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    task = await writing_service.create_writing_task(
        db=db,
        title=body.title,
        prompt=body.prompt,
        instructions=body.instructions,
        word_limit=body.word_limit,
        recommended_time_minutes=body.recommended_time_minutes,
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
        admin_profile_id=admin_profile.id,
    )
    return _task_to_response(task)


@router.get("/tasks", response_model=list[WritingTaskResponse])
async def list_writing_tasks(
    status: str | None = None,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    tasks = await writing_service.list_writing_tasks(db, status_str=status)
    return [_task_to_response(t) for t in tasks]


@router.patch("/tasks/{task_id}/publish", response_model=WritingTaskResponse)
async def publish_writing_task(
    task_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    task = await writing_service.update_writing_task_status(
        task_id, WritingTaskStatus.published, db
    )
    return _task_to_response(task)


@router.patch("/tasks/{task_id}/archive", response_model=WritingTaskResponse)
async def archive_writing_task(
    task_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    task = await writing_service.update_writing_task_status(
        task_id, WritingTaskStatus.archived, db
    )
    return _task_to_response(task)


# ── Submissions (review) ───────────────────────────────────────────────────


@router.get("/submissions", response_model=list[WritingSubmissionListItem])
async def list_all_submissions(
    task_id: str | None = None,
    status: str | None = None,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_service.list_all_submissions(
        db, task_id=task_id, status_str=status
    )


# ── Human review workflow (M5.1) ────────────────────────────────────────────


@router.get("/reviews")
async def list_reviews(
    status: str | None = None,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_review_service.list_reviews(db, status_str=status)


@router.get("/reviews/{review_id}")
async def get_review(
    review_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_review_service.get_review_detail(
        review_id, actor_user_id=admin_profile.user_id, db=db
    )


@router.post("/reviews/{review_id}/assign")
async def assign_review(
    review_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    # Self-assignment for V1 (reviewer balancing is out of scope).
    return await writing_review_service.assign_review(
        review_id,
        reviewer_admin_id=admin_profile.id,
        actor_user_id=admin_profile.user_id,
        db=db,
    )


@router.post("/reviews/{review_id}/feedback")
async def add_feedback(
    review_id: str,
    body: WritingFeedbackCreate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_review_service.add_feedback(
        review_id,
        overall_comment=body.overall_comment,
        dimensions=body.dimensions,
        admin_profile_id=admin_profile.id,
        actor_user_id=admin_profile.user_id,
        db=db,
    )


@router.post("/reviews/{review_id}/publish")
async def publish_review(
    review_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_review_service.publish_review(
        review_id, actor_user_id=admin_profile.user_id, db=db
    )


def _task_to_response(t) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "prompt": t.prompt,
        "instructions": t.instructions,
        "word_limit": t.word_limit,
        "recommended_time_minutes": t.recommended_time_minutes,
        "subject_id": t.subject_id,
        "exam_type_id": t.exam_type_id,
        "status": t.status.value,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
