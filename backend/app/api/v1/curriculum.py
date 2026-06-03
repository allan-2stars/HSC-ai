from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.curriculum import (
    CoverageReportResponse,
    DashboardSummaryResponse,
    FrameworkCreate,
    FrameworkResponse,
    OutcomeCreate,
    OutcomeResponse,
    QuestionMappingCreate,
    QuestionMappingResponse,
    UnmappedQuestionItem,
)
from app.services import curriculum_service

router = APIRouter(tags=["curriculum"])


# ── Frameworks ───────────────────────────────────────────────────────────────

@router.get("/curriculum/frameworks", response_model=list[FrameworkResponse])
async def list_frameworks(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.list_frameworks(db)


@router.post("/curriculum/frameworks", response_model=FrameworkResponse, status_code=201)
async def create_framework(
    body: FrameworkCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.create_framework(
        name=body.name,
        db=db,
        description=body.description,
        exam_type_id=body.exam_type_id,
        version=body.version,
    )


@router.get("/curriculum/frameworks/{framework_id}", response_model=FrameworkResponse)
async def get_framework(
    framework_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.get_framework(framework_id, db)


# ── Outcomes ─────────────────────────────────────────────────────────────────

@router.get("/curriculum/outcomes", response_model=list[OutcomeResponse])
async def list_outcomes(
    framework_id: str | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.list_outcomes(db, framework_id=framework_id)


@router.post("/curriculum/outcomes", response_model=OutcomeResponse, status_code=201)
async def create_outcome(
    body: OutcomeCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.create_outcome(
        framework_id=body.framework_id,
        code=body.code,
        title=body.title,
        db=db,
        description=body.description,
        sort_order=body.sort_order,
    )


# ── Question Mappings ────────────────────────────────────────────────────────

@router.post("/curriculum/question-mappings", response_model=QuestionMappingResponse, status_code=201)
async def create_mapping(
    body: QuestionMappingCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.create_question_mapping(
        question_id=body.question_id,
        outcome_id=body.outcome_id,
        db=db,
        weight=body.weight,
    )


@router.delete("/curriculum/question-mappings/{mapping_id}", status_code=204)
async def delete_mapping(
    mapping_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await curriculum_service.delete_question_mapping(mapping_id, db)


# ── Coverage ─────────────────────────────────────────────────────────────────

@router.get(
    "/curriculum/coverage/{framework_id}",
    response_model=CoverageReportResponse,
)
async def framework_coverage(
    framework_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.get_framework_coverage(framework_id, db)


@router.get("/curriculum/unmapped-questions", response_model=list[UnmappedQuestionItem])
async def unmapped_questions(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.get_unmapped_questions(db)


@router.get("/curriculum/dashboard", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await curriculum_service.get_dashboard_summary(db)
