from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.content import (
    ExamTypeCreateRequest,
    ExamTypeResponse,
    ExamTypeUpdateRequest,
    SkillTagCreateRequest,
    SkillTagResponse,
    SkillTagUpdateRequest,
    SubjectCreateRequest,
    SubjectResponse,
    SubjectUpdateRequest,
    TopicCreateRequest,
    TopicResponse,
    TopicUpdateRequest,
)
from app.services import content_service

router = APIRouter(prefix="/admin", tags=["admin-content"])


# ── Subjects ──────────────────────────────────────────────────────────────────

@router.post("/subjects", response_model=SubjectResponse, status_code=201)
async def create_subject(
    body: SubjectCreateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.create_subject(code=body.code, name=body.name, db=db)


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.list_subjects(db=db)


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.get_subject(subject_id=subject_id, db=db)


@router.patch("/subjects/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    body: SubjectUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.update_subject(
        subject_id=subject_id, name=body.name, is_active=body.is_active, db=db
    )


# ── ExamTypes ─────────────────────────────────────────────────────────────────

@router.post("/exam-types", response_model=ExamTypeResponse, status_code=201)
async def create_exam_type(
    body: ExamTypeCreateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.create_exam_type(code=body.code, name=body.name, db=db)


@router.get("/exam-types", response_model=list[ExamTypeResponse])
async def list_exam_types(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.list_exam_types(db=db)


@router.get("/exam-types/{exam_type_id}", response_model=ExamTypeResponse)
async def get_exam_type(
    exam_type_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.get_exam_type(exam_type_id=exam_type_id, db=db)


@router.patch("/exam-types/{exam_type_id}", response_model=ExamTypeResponse)
async def update_exam_type(
    exam_type_id: str,
    body: ExamTypeUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.update_exam_type(
        exam_type_id=exam_type_id, name=body.name, is_active=body.is_active, db=db
    )


# ── Topics ────────────────────────────────────────────────────────────────────

@router.post("/topics", response_model=TopicResponse, status_code=201)
async def create_topic(
    body: TopicCreateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.create_topic(
        subject_id=body.subject_id, name=body.name, description=body.description, db=db
    )


@router.get("/topics", response_model=list[TopicResponse])
async def list_topics(
    subject_id: str | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.list_topics(db=db, subject_id=subject_id)


@router.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.get_topic(topic_id=topic_id, db=db)


@router.patch("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    body: TopicUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.update_topic(
        topic_id=topic_id,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
        db=db,
    )


# ── SkillTags ─────────────────────────────────────────────────────────────────

@router.post("/skill-tags", response_model=SkillTagResponse, status_code=201)
async def create_skill_tag(
    body: SkillTagCreateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.create_skill_tag(
        name=body.name, subject_id=body.subject_id, db=db
    )


@router.get("/skill-tags", response_model=list[SkillTagResponse])
async def list_skill_tags(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.list_skill_tags(db=db)


@router.get("/skill-tags/{skill_tag_id}", response_model=SkillTagResponse)
async def get_skill_tag(
    skill_tag_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.get_skill_tag(skill_tag_id=skill_tag_id, db=db)


@router.patch("/skill-tags/{skill_tag_id}", response_model=SkillTagResponse)
async def update_skill_tag(
    skill_tag_id: str,
    body: SkillTagUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.update_skill_tag(
        skill_tag_id=skill_tag_id, name=body.name, is_active=body.is_active, db=db
    )
