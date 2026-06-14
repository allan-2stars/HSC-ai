from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.user import AdminProfile, User
from app.schemas.quality_schema import (
    OutcomeQualityItem,
    ProviderComparisonResponse,
    QualityDashboardResponse,
    QualityReviewCreate,
    QualityReviewResponse,
    RegenerationCandidateItem,
)
from app.services import quality_service

router = APIRouter(prefix="/admin/content", tags=["admin-quality"])


# ── Create Review ────────────────────────────────────────────────────────────

@router.post("/quality-review", response_model=QualityReviewResponse, status_code=201)
async def create_quality_review(
    body: QualityReviewCreate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    review = await quality_service.create_quality_review(
        question_id=body.question_id,
        admin_id=admin_profile.id,
        db=db,
        correctness_score=body.correctness_score,
        outcome_alignment_score=body.outcome_alignment_score,
        difficulty_score=body.difficulty_score,
        explanation_score=body.explanation_score,
        overall_score=body.overall_score,
        notes=body.notes,
    )
    return {
        "id": review.id,
        "question_id": review.question_id,
        "reviewer_admin_id": review.reviewer_admin_id,
        "correctness_score": review.correctness_score,
        "outcome_alignment_score": review.outcome_alignment_score,
        "difficulty_score": review.difficulty_score,
        "explanation_score": review.explanation_score,
        "overall_score": review.overall_score,
        "notes": review.notes,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


# ── List Reviews ─────────────────────────────────────────────────────────────

@router.get("/quality-reviews", response_model=list[QualityReviewResponse])
async def list_quality_reviews(
    question_id: str | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if question_id:
        reviews = await quality_service.get_question_reviews(question_id, db)
    else:
        reviews = await quality_service.list_all_reviews(db)
    return [
        {
            "id": r.id,
            "question_id": r.question_id,
            "reviewer_admin_id": r.reviewer_admin_id,
            "correctness_score": r.correctness_score,
            "outcome_alignment_score": r.outcome_alignment_score,
            "difficulty_score": r.difficulty_score,
            "explanation_score": r.explanation_score,
            "overall_score": r.overall_score,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reviews
    ]


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/quality-dashboard", response_model=QualityDashboardResponse)
async def quality_dashboard(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await quality_service.get_quality_dashboard(db)


# ── Provider Comparison ──────────────────────────────────────────────────────

@router.get("/quality-by-provider", response_model=ProviderComparisonResponse)
async def quality_by_provider(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await quality_service.get_quality_by_provider(db)
    return data


# ── Outcome Quality ──────────────────────────────────────────────────────────

@router.get("/quality-by-outcome", response_model=list[OutcomeQualityItem])
async def quality_by_outcome(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await quality_service.get_quality_by_outcome(db)


# ── Regeneration Candidates ──────────────────────────────────────────────────

@router.get("/quality-regeneration-candidates", response_model=list[RegenerationCandidateItem])
async def regeneration_candidates(
    limit: int = Query(default=50, le=200),
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await quality_service.get_regeneration_candidates(db, limit=limit)
