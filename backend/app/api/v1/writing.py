from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.writing_schema import (
    WritingDisputeCreate,
    WritingSubmissionResponse,
    WritingSubmissionSave,
)
from app.services import writing_analytics_service, writing_dispute_service, writing_portfolio_service, writing_review_service, writing_rubric_service, writing_service
from app.services.family_service import get_student_profile

router = APIRouter(prefix="/writing", tags=["writing"])


# ── Available Tasks ───────────────────────────────────────────────────────


@router.get("/tasks")
async def list_available_tasks(
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    return await writing_service.list_student_available_tasks(profile.id, db)


# ── Submissions ───────────────────────────────────────────────────────────


@router.post("/tasks/{task_id}/start")
async def start_writing(
    task_id: str,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    sub = await writing_service.get_or_create_submission(task_id, profile.id, db)
    return _sub_to_response(sub)


@router.patch("/submissions/{submission_id}/save")
async def save_writing(
    submission_id: str,
    body: WritingSubmissionSave,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    sub = await writing_service.save_submission(
        submission_id, profile.id, body.content, db
    )
    return _sub_to_response(sub)


@router.post("/submissions/{submission_id}/submit")
async def submit_writing(
    submission_id: str,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    sub = await writing_service.submit_submission(
        submission_id, profile.id, db, student_user_id=student.id
    )
    return _sub_to_response(sub)


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: str,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    sub = await writing_service.get_student_submission(submission_id, profile.id, db)
    return _sub_to_response(sub)


@router.get("/submissions")
async def list_my_submissions(
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    return await writing_service.list_student_submissions(profile.id, db)


@router.get("/submissions/{submission_id}/feedback")
async def get_submission_feedback(
    submission_id: str,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    # Ownership check first (403 if not the student's own submission).
    await writing_service.get_student_submission(submission_id, profile.id, db)
    return await writing_review_service.get_published_feedback_for_submission(submission_id, db)


@router.get("/submissions/{submission_id}/rubric")
async def get_submission_rubric(
    submission_id: str,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    await writing_service.get_student_submission(submission_id, profile.id, db)
    return await writing_rubric_service.get_published_rubric_for_submission(submission_id, db)


# ── Disputes (M5.5) ───────────────────────────────────────────────────────


@router.post("/submissions/{submission_id}/disputes", status_code=201)
async def create_dispute(
    submission_id: str,
    body: WritingDisputeCreate,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    await writing_service.get_student_submission(submission_id, profile.id, db)
    # Resolve review_id from submission
    from sqlalchemy import select as _select
    from app.models.writing import WritingReview as _WritingReview
    review_result = await db.execute(
        _select(_WritingReview.id).where(_WritingReview.submission_id == submission_id)
    )
    review_row = review_result.fetchone()
    if not review_row:
        raise HTTPException(status_code=404, detail="Review not found")
    return await writing_dispute_service.create_dispute(
        review_row[0], body.reason, "student", student.id, profile.id, db
    )


@router.get("/submissions/{submission_id}/disputes")
async def list_my_disputes(
    submission_id: str,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    await writing_service.get_student_submission(submission_id, profile.id, db)
    from sqlalchemy import select as _select
    from app.models.writing import WritingReview as _WritingReview
    review_result = await db.execute(
        _select(_WritingReview.id).where(_WritingReview.submission_id == submission_id)
    )
    review_row = review_result.fetchone()
    if not review_row:
        raise HTTPException(status_code=404, detail="Review not found")
    return await writing_dispute_service.list_disputes_for_review(
        review_row[0], profile.id, "student", db
    )


# ── Analytics (M5.7) ──────────────────────────────────────────────────────


@router.get("/analytics/me")
async def get_my_analytics(
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    return await writing_analytics_service.build_student_analytics(profile.id, db)


@router.get("/analytics/me/tasks")
async def get_my_task_analytics(
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    return await writing_analytics_service.build_task_analytics(profile.id, db)


# ── Portfolio (M5.8) ──────────────────────────────────────────────────────


@router.get("/portfolio/me")
async def get_my_portfolio(
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    return await writing_portfolio_service.build_portfolio_list(profile.id, db)


@router.get("/portfolio/me/items/{submission_id}")
async def get_my_portfolio_item(
    submission_id: str,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_student_profile(student.id, db)
    return await writing_portfolio_service.build_portfolio_detail(submission_id, profile.id, db)


def _sub_to_response(sub) -> dict:
    return {
        "id": sub.id,
        "writing_task_id": sub.writing_task_id,
        "student_id": sub.student_id,
        "content": sub.content,
        "word_count": sub.word_count,
        "status": sub.status.value,
        "started_at": sub.started_at.isoformat() if sub.started_at else None,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
    }
