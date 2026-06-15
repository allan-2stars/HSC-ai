"""Content quality review — scoring, aggregation, provider/outcome analytics."""
from sqlalchemy import func, select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIGenerationJob
from app.models.curriculum import CurriculumOutcome, QuestionOutcomeMapping
from app.models.quality import QuestionQualityReview
from app.models.question import ContentOwnershipType, Question, QuestionStatus


# Ownership types that are NEVER allowed in quality review (unsafe/copyright).
_BLOCKED_OWNERSHIP = {
    ContentOwnershipType.restricted_reference_only,
}

# Lifecycle statuses that are NOT allowed in quality review (not yet in or past review pipeline).
_BLOCKED_STATUS = {
    QuestionStatus.draft,
    QuestionStatus.archived,
    QuestionStatus.rejected,
}


async def _validate_question_reviewable(question: Question) -> None:
    """Raise HTTPException if the question cannot be quality-reviewed.

    Two independent gates:
    1. Ownership safety — restricted content must never be reviewed.
    2. Lifecycle status — draft (not ready), archived/rejected (dead).
    internal_draft ownership is allowed when the question has reached review/approved/published status.
    """
    from fastapi import HTTPException, status

    if question.content_ownership in _BLOCKED_OWNERSHIP:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Questions with content_ownership '{question.content_ownership.value}' cannot be quality-reviewed",
        )
    if question.status in _BLOCKED_STATUS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Questions with status '{question.status.value}' cannot be quality-reviewed",
        )


# ── CRUD ─────────────────────────────────────────────────────────────────────


async def create_quality_review(
    question_id: str,
    admin_id: str,
    db: AsyncSession,
    correctness_score: int = 3,
    outcome_alignment_score: int = 3,
    difficulty_score: int = 3,
    explanation_score: int = 3,
    overall_score: int = 3,
    notes: str | None = None,
) -> QuestionQualityReview:
    from fastapi import HTTPException

    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    await _validate_question_reviewable(question)

    for field, name in [
        (correctness_score, "correctness_score"),
        (outcome_alignment_score, "outcome_alignment_score"),
        (difficulty_score, "difficulty_score"),
        (explanation_score, "explanation_score"),
        (overall_score, "overall_score"),
    ]:
        if field not in range(1, 6):
            raise HTTPException(status_code=422, detail=f"{name} must be 1-5")

    review = QuestionQualityReview(
        question_id=question_id,
        reviewer_admin_id=admin_id,
        correctness_score=correctness_score,
        outcome_alignment_score=outcome_alignment_score,
        difficulty_score=difficulty_score,
        explanation_score=explanation_score,
        overall_score=overall_score,
        notes=notes,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


async def get_question_reviews(question_id: str, db: AsyncSession) -> list[QuestionQualityReview]:
    result = await db.execute(
        select(QuestionQualityReview)
        .where(QuestionQualityReview.question_id == question_id)
        .order_by(QuestionQualityReview.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all_reviews(
    db: AsyncSession, limit: int = 200
) -> list[QuestionQualityReview]:
    result = await db.execute(
        select(QuestionQualityReview)
        .order_by(QuestionQualityReview.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ── Dashboard ────────────────────────────────────────────────────────────────


async def get_quality_dashboard(db: AsyncSession) -> dict:
    """Aggregate quality metrics using SQL — no unbounded table scan."""
    result = await db.execute(
        select(
            func.count(QuestionQualityReview.id).label("total_reviews"),
            func.count(distinct(QuestionQualityReview.question_id)).label("unique_questions"),
            func.avg(QuestionQualityReview.correctness_score).label("avg_correctness"),
            func.avg(QuestionQualityReview.outcome_alignment_score).label("avg_outcome_alignment"),
            func.avg(QuestionQualityReview.difficulty_score).label("avg_difficulty"),
            func.avg(QuestionQualityReview.explanation_score).label("avg_explanation"),
            func.avg(QuestionQualityReview.overall_score).label("avg_overall"),
            func.count(distinct(QuestionQualityReview.question_id)).filter(
                QuestionQualityReview.overall_score < 3
            ).label("needs_revision_distinct"),
        )
    )
    row = result.one()
    total = row.total_reviews

    if total == 0:
        return {
            "total_reviews": 0,
            "unique_questions_reviewed": 0,
            "average_scores": {"correctness": 0, "outcome_alignment": 0, "difficulty": 0, "explanation": 0, "overall": 0},
            "needs_revision_count": 0,
            "reviews": [],
        }

    avg = {
        "correctness": float(round(row.avg_correctness, 1)) if row.avg_correctness else 0,
        "outcome_alignment": float(round(row.avg_outcome_alignment, 1)) if row.avg_outcome_alignment else 0,
        "difficulty": float(round(row.avg_difficulty, 1)) if row.avg_difficulty else 0,
        "explanation": float(round(row.avg_explanation, 1)) if row.avg_explanation else 0,
        "overall": float(round(row.avg_overall, 1)) if row.avg_overall else 0,
    }

    # Fetch the most recent 50 reviews deterministically
    recent_result = await db.execute(
        select(QuestionQualityReview)
        .order_by(QuestionQualityReview.created_at.desc())
        .limit(50)
    )
    recent_reviews = list(recent_result.scalars().all())

    return {
        "total_reviews": total,
        "unique_questions_reviewed": row.unique_questions,
        "average_scores": avg,
        "needs_revision_count": row.needs_revision_distinct,
        "reviews": _to_list(recent_reviews),
    }


# ── Provider Comparison ──────────────────────────────────────────────────────


async def get_quality_by_provider(db: AsyncSession) -> dict:
    """Compare quality scores by content source_type and AI provider.

    Returns a dict with 'source' and 'providers' keys (named, not positional).
    """
    result = await db.execute(
        select(
            QuestionQualityReview.overall_score,
            Question.source_type,
        )
        .join(Question, Question.id == QuestionQualityReview.question_id)
    )
    rows = result.fetchall()

    by_source: dict[str, dict] = {}
    for score, source in rows:
        s = str(source.value) if hasattr(source, "value") else str(source)
        if s not in by_source:
            by_source[s] = {"scores": [], "count": 0, "total": 0}
        by_source[s]["scores"].append(score)
        by_source[s]["count"] += 1
        by_source[s]["total"] += score

    source_results = []
    for source, data in sorted(by_source.items()):
        avg = round(data["total"] / data["count"], 1) if data["count"] > 0 else 0
        source_results.append({
            "source": source,
            "reviewed_count": data["count"],
            "average_score": avg,
        })

    # AI provider breakdown from AIGenerationJob
    result = await db.execute(
        select(AIGenerationJob.provider, AIGenerationJob.saved_count, AIGenerationJob.rejected_count)
        .where(AIGenerationJob.status == "completed")
    )
    provider_rows = result.fetchall()

    by_provider: dict[str, dict] = {}
    for prov, saved, rejected in provider_rows:
        p = str(prov)
        if p not in by_provider:
            by_provider[p] = {"saved": 0, "rejected": 0}
        by_provider[p]["saved"] += saved
        by_provider[p]["rejected"] += rejected

    provider_results = []
    for prov, data in sorted(by_provider.items()):
        total = data["saved"] + data["rejected"]
        rejection_rate = round((data["rejected"] / total) * 100, 1) if total > 0 else 0
        pub_rate = round((data["saved"] / total) * 100, 1) if total > 0 else 0
        provider_results.append({
            "provider": prov,
            "saved_count": data["saved"],
            "rejected_count": data["rejected"],
            "rejection_rate": rejection_rate,
            "publication_rate": pub_rate,
        })

    return {"source": source_results, "providers": provider_results}


# ── Outcome Analytics ────────────────────────────────────────────────────────


async def get_quality_by_outcome(db: AsyncSession) -> list[dict]:
    """Quality scores aggregated by curriculum outcome — single grouped query including published counts."""
    result = await db.execute(
        select(
            CurriculumOutcome.code,
            CurriculumOutcome.title,
            func.count(QuestionQualityReview.id).label("reviewed_count"),
            func.avg(QuestionQualityReview.overall_score).label("avg_quality"),
            func.count(QuestionQualityReview.id).filter(
                QuestionQualityReview.overall_score < 3
            ).label("needs_regen"),
            func.count(Question.id).filter(Question.status == QuestionStatus.published).label("published_count"),
        )
        .select_from(CurriculumOutcome)
        .join(QuestionOutcomeMapping, QuestionOutcomeMapping.outcome_id == CurriculumOutcome.id)
        .join(Question, Question.id == QuestionOutcomeMapping.question_id)
        .outerjoin(QuestionQualityReview, QuestionQualityReview.question_id == Question.id)
        .group_by(CurriculumOutcome.code, CurriculumOutcome.title)
        .order_by(func.avg(QuestionQualityReview.overall_score).asc().nulls_last())
    )
    rows = result.fetchall()

    return [
        {
            "outcome_code": code,
            "outcome_title": title,
            "total_questions": published_count,
            "reviewed_count": reviewed_count,
            "average_quality": float(round(avg_quality, 1)) if avg_quality else 0,
            "needs_regeneration": needs_regen,
        }
        for code, title, reviewed_count, avg_quality, needs_regen, published_count in rows
    ]


# ── Regeneration Candidates ──────────────────────────────────────────────────


async def get_regeneration_candidates(db: AsyncSession, limit: int = 50) -> list[dict]:
    """Find questions with overall_score < 3 flagged for regeneration."""
    result = await db.execute(
        select(QuestionQualityReview, Question.source_type, Question.status)
        .join(Question, Question.id == QuestionQualityReview.question_id)
        .where(QuestionQualityReview.overall_score < 3)
        .order_by(QuestionQualityReview.overall_score, QuestionQualityReview.created_at.desc())
        .limit(limit)
    )
    rows = result.fetchall()

    candidates = []
    for review, source, qstatus in rows:
        candidates.append({
            "question_id": review.question_id,
            "review_id": review.id,
            "overall_score": review.overall_score,
            "source_type": str(source.value) if hasattr(source, "value") else str(source),
            "question_status": str(qstatus.value) if hasattr(qstatus, "value") else str(qstatus),
            "notes": review.notes,
        })
    return candidates


def _to_list(reviews: list[QuestionQualityReview]) -> list[dict]:
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
