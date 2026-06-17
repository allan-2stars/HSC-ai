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
from app.services import family_service, writing_review_service, writing_service

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
