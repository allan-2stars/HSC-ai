from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_parent, get_current_user
from app.models.user import User
from app.schemas.user import (
    MeResponse,
    StudentCreateRequest,
    StudentResponse,
    StudentUpdateRequest,
)
from app.schemas.writing_schema import WritingDisputeCreate
from app.services import (
    family_service,
    writing_analytics_service,
    writing_dispute_service,
    writing_portfolio_service,
    writing_review_service,
    writing_rubric_service,
    writing_service,
)

router = APIRouter(tags=["parents"])


@router.get("/me", response_model=MeResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return MeResponse.model_validate(current_user)


@router.post("/parents/students", response_model=StudentResponse, status_code=201)
async def create_student(
    body: StudentCreateRequest,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    profile, login_email, temp_password = await family_service.create_student(
        parent_id=parent_profile.id,
        display_name=body.display_name,
        year_level=body.year_level,
        initial_password=body.initial_password,
        db=db,
        actor_user_id=parent.id,
    )
    return StudentResponse(
        id=profile.id,
        display_name=profile.display_name,
        year_level=profile.year_level,
        first_login_completed=profile.first_login_completed,
        login_email=login_email,
        temp_password=temp_password,
    )


@router.get("/parents/students", response_model=list[StudentResponse])
async def list_students(
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    profiles = await family_service.list_students(parent_profile.id, db)
    return [
        StudentResponse(
            id=p.id,
            display_name=p.display_name,
            year_level=p.year_level,
            first_login_completed=p.first_login_completed,
        )
        for p in profiles
    ]


@router.patch("/parents/students/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    body: StudentUpdateRequest,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    profile = await family_service.update_student(
        student_id=student_id,
        parent_id=parent_profile.id,
        display_name=body.display_name,
        year_level=body.year_level,
        db=db,
    )
    return StudentResponse(
        id=profile.id,
        display_name=profile.display_name,
        year_level=profile.year_level,
        first_login_completed=profile.first_login_completed,
    )


@router.delete("/parents/students/{student_id}", status_code=204)
async def delete_student(
    student_id: str,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    await family_service.deactivate_student(
        student_id=student_id,
        parent_id=parent_profile.id,
        db=db,
        actor_user_id=parent.id,
    )


@router.get("/parents/students/{student_id}/writing")
async def list_student_writing(
    student_id: str,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    students = await family_service.list_students(parent_profile.id, db)
    student_ids = [s.id for s in students]
    return await writing_service.get_student_submissions_for_parent(
        student_id, student_ids, db
    )


@router.get("/parents/students/{student_id}/writing/{submission_id}/feedback")
async def get_student_writing_feedback(
    student_id: str,
    submission_id: str,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    students = await family_service.list_students(parent_profile.id, db)
    if student_id not in [s.id for s in students]:
        raise HTTPException(status_code=403, detail="Not your student")
    # Verify the submission belongs to this student (403 if not).
    await writing_service.get_student_submission(submission_id, student_id, db)
    return await writing_review_service.get_published_feedback_for_submission(submission_id, db)


@router.get("/parents/students/{student_id}/writing/{submission_id}/rubric")
async def get_student_writing_rubric(
    student_id: str,
    submission_id: str,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    students = await family_service.list_students(parent_profile.id, db)
    if student_id not in [s.id for s in students]:
        raise HTTPException(status_code=403, detail="Not your student")
    await writing_service.get_student_submission(submission_id, student_id, db)
    return await writing_rubric_service.get_published_rubric_for_submission(submission_id, db)


@router.post("/parents/students/{student_id}/writing/{submission_id}/disputes", status_code=201)
async def create_parent_dispute(
    student_id: str,
    submission_id: str,
    body: WritingDisputeCreate,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    students = await family_service.list_students(parent_profile.id, db)
    if student_id not in [s.id for s in students]:
        raise HTTPException(status_code=403, detail="Not your student")
    from sqlalchemy import select as _select
    from app.models.writing import WritingReview as _WritingReview
    review_result = await db.execute(
        _select(_WritingReview.id).where(_WritingReview.submission_id == submission_id)
    )
    review_row = review_result.fetchone()
    if not review_row:
        raise HTTPException(status_code=404, detail="Review not found")
    return await writing_dispute_service.create_dispute(
        review_row[0], body.reason, "parent", parent.id, student_id, db
    )


# ── Writing Analytics (M5.7) ──────────────────────────────────────────────


@router.get("/parents/students/{student_id}/writing/analytics")
async def get_student_writing_analytics(
    student_id: str,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    students = await family_service.list_students(parent_profile.id, db)
    if student_id not in [s.id for s in students]:
        raise HTTPException(status_code=403, detail="Not your student")
    return await writing_analytics_service.build_student_analytics(student_id, db)


@router.get("/parents/students/{student_id}/writing/analytics/tasks")
async def get_student_task_analytics(
    student_id: str,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    students = await family_service.list_students(parent_profile.id, db)
    if student_id not in [s.id for s in students]:
        raise HTTPException(status_code=403, detail="Not your student")
    return await writing_analytics_service.build_task_analytics(student_id, db)


# ── Portfolio (M5.8) ──────────────────────────────────────────────────────


@router.get("/parents/students/{student_id}/writing/portfolio")
async def get_student_portfolio(
    student_id: str,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    students = await family_service.list_students(parent_profile.id, db)
    if student_id not in [s.id for s in students]:
        raise HTTPException(status_code=403, detail="Not your student")
    return await writing_portfolio_service.build_portfolio_list(student_id, db)


@router.get("/parents/students/{student_id}/writing/portfolio/items/{submission_id}")
async def get_student_portfolio_item(
    student_id: str,
    submission_id: str,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent.id, db)
    students = await family_service.list_students(parent_profile.id, db)
    if student_id not in [s.id for s in students]:
        raise HTTPException(status_code=403, detail="Not your student")
    return await writing_portfolio_service.build_portfolio_detail(submission_id, student_id, db)
