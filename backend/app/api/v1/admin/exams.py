from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.exam import ExamInstanceStatus, ExamTemplateStatus
from app.models.user import AdminProfile, User
from app.schemas.exam import (
    ExamInstanceCreate,
    ExamInstanceListResponse,
    ExamInstanceResponse,
    ExamSectionCreate,
    ExamSectionQuestionCreate,
    ExamSectionQuestionResponse,
    ExamSectionResponse,
    ExamTemplateCreate,
    ExamTemplateListResponse,
    ExamTemplateResponse,
    ExamTemplateStatusUpdate,
)
from app.services import exam_service

router = APIRouter(prefix="/admin", tags=["admin-exams"])


# ── ExamTemplate ─────────────────────────────────────────────────────────────

@router.post("/exam-templates", response_model=ExamTemplateResponse, status_code=201)
async def create_template(
    body: ExamTemplateCreate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.create_exam_template(
        title=body.title,
        exam_type_id=body.exam_type_id,
        duration_minutes=body.duration_minutes,
        created_by_admin_id=admin_profile.id,
        db=db,
        description=body.description,
        subject_id=body.subject_id,
        year_level=body.year_level,
    )


@router.get("/exam-templates", response_model=list[ExamTemplateListResponse])
async def list_templates(
    status: ExamTemplateStatus | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.list_exam_templates(db=db, status_filter=status)


@router.get("/exam-templates/{template_id}", response_model=ExamTemplateResponse)
async def get_template(
    template_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.get_exam_template(template_id=template_id, db=db)


@router.patch("/exam-templates/{template_id}/status", response_model=ExamTemplateResponse)
async def update_template_status(
    template_id: str,
    body: ExamTemplateStatusUpdate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.update_template_status(
        template_id=template_id, new_status=body.status, db=db
    )


# ── ExamSection ──────────────────────────────────────────────────────────────

@router.post(
    "/exam-templates/{template_id}/sections",
    response_model=ExamSectionResponse,
    status_code=201,
)
async def create_section(
    template_id: str,
    body: ExamSectionCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.create_exam_section(
        template_id=template_id,
        title=body.title,
        db=db,
        order_index=body.order_index,
        duration_minutes=body.duration_minutes,
        instructions=body.instructions,
    )


@router.post(
    "/exam-templates/{template_id}/sections/{section_id}/questions",
    response_model=ExamSectionQuestionResponse,
    status_code=201,
)
async def add_question_to_section(
    template_id: str,
    section_id: str,
    body: ExamSectionQuestionCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.add_question_to_section(
        section_id=section_id,
        question_id=body.question_id,
        db=db,
        order_index=body.order_index,
        marks=body.marks,
    )


# ── ExamInstance ─────────────────────────────────────────────────────────────

@router.post("/exam-instances", response_model=ExamInstanceResponse, status_code=201)
async def create_instance(
    body: ExamInstanceCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.create_exam_instance(
        template_id=body.template_id,
        db=db,
        title=body.title,
    )


@router.post("/exam-instances/{instance_id}/publish", response_model=ExamInstanceResponse)
async def publish_instance(
    instance_id: str,
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.publish_exam_instance(
        instance_id=instance_id, db=db, admin_user_id=admin_user.id
    )


@router.get("/exam-instances", response_model=list[ExamInstanceListResponse])
async def list_instances(
    status: ExamInstanceStatus | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.list_exam_instances(db=db, status_filter=status)


@router.get("/exam-instances/{instance_id}", response_model=ExamInstanceResponse)
async def get_instance(
    instance_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.get_exam_instance(instance_id=instance_id, db=db)
