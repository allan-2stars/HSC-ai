from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.question import QuestionStatus
from app.models.user import AdminProfile, User
from app.schemas.question import (
    QuestionCreateRequest,
    QuestionResponse,
    QuestionStatusRequest,
    QuestionVersionCreateRequest,
    QuestionVersionResponse,
)
from app.services import question_service

router = APIRouter(prefix="/admin", tags=["admin-questions"])


@router.post("/questions", response_model=QuestionResponse, status_code=201)
async def create_question(
    body: QuestionCreateRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.create_question(
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
        year_level=body.year_level,
        difficulty=body.difficulty,
        question_type=body.question_type,
        source_type=body.source_type,
        content_ownership=body.content_ownership,
        stem=body.stem,
        full_explanation=body.full_explanation,
        created_by_admin_id=admin_profile.id,
        db=db,
        topic_id=body.topic_id,
        copyright_note=body.copyright_note,
        correct_answer=body.correct_answer,
        marks=body.marks,
        options_json=body.options_json,
    )


@router.get("/questions", response_model=list[QuestionResponse])
async def list_questions(
    status: QuestionStatus | None = None,
    subject_id: str | None = None,
    exam_type_id: str | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_questions(
        db=db,
        status_filter=status,
        subject_id=subject_id,
        exam_type_id=exam_type_id,
    )


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.get_question(question_id=question_id, db=db)


@router.patch("/questions/{question_id}/status", response_model=QuestionResponse)
async def update_question_status(
    question_id: str,
    body: QuestionStatusRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.transition_status(
        question_id=question_id, new_status=body.status, db=db
    )


@router.post(
    "/questions/{question_id}/versions",
    response_model=QuestionVersionResponse,
    status_code=201,
)
async def add_question_version(
    question_id: str,
    body: QuestionVersionCreateRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.add_version(
        question_id=question_id,
        stem=body.stem,
        full_explanation=body.full_explanation,
        created_by_admin_id=admin_profile.id,
        db=db,
        correct_answer=body.correct_answer,
        marks=body.marks,
        options_json=body.options_json,
    )


@router.get(
    "/questions/{question_id}/versions",
    response_model=list[QuestionVersionResponse],
)
async def list_question_versions(
    question_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_versions(question_id=question_id, db=db)
