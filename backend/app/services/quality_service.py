"""Content quality review — scoring, aggregation, provider/outcome analytics."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIGenerationJob
from app.models.curriculum import CurriculumOutcome, QuestionOutcomeMapping
from app.models.quality import QuestionQualityReview
from app.models.question import Question, QuestionStatus, SourceType


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
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

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
    """Aggregate quality metrics across all reviewed questions."""
    result = await db.execute(select(QuestionQualityReview))
    reviews = list(result.scalars().all())

    if not reviews:
        return _empty_dashboard()

    total = len(reviews)
    avg = {
        "correctness": round(sum(r.correctness_score for r in reviews) / total, 1),
        "outcome_alignment": round(sum(r.outcome_alignment_score for r in reviews) / total, 1),
        "difficulty": round(sum(r.difficulty_score for r in reviews) / total, 1),
        "explanation": round(sum(r.explanation_score for r in reviews) / total, 1),
        "overall": round(sum(r.overall_score for r in reviews) / total, 1),
    }

    unique_questions = len({r.question_id for r in reviews})
    needs_revision = sum(1 for r in reviews if r.overall_score < 3)

    return {
        "total_reviews": total,
        "unique_questions_reviewed": unique_questions,
        "average_scores": avg,
        "needs_revision_count": needs_revision,
        "reviews": _to_list(reviews[:50]),
    }


def _empty_dashboard():
    return {
        "total_reviews": 0,
        "unique_questions_reviewed": 0,
        "average_scores": {"correctness": 0, "outcome_alignment": 0, "difficulty": 0, "explanation": 0, "overall": 0},
        "needs_revision_count": 0,
        "reviews": [],
    }


# ── Provider Comparison ──────────────────────────────────────────────────────


async def get_quality_by_provider(db: AsyncSession) -> list[dict]:
    """Compare quality scores by content source_type and AI provider."""
    # Get all reviews with question source_type
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

    return [{"source": source_results}, {"providers": provider_results}]


# ── Outcome Analytics ────────────────────────────────────────────────────────


async def get_quality_by_outcome(db: AsyncSession) -> list[dict]:
    """Quality scores aggregated by curriculum outcome."""
    result = await db.execute(
        select(
            CurriculumOutcome.code,
            CurriculumOutcome.title,
            QuestionQualityReview.overall_score,
        )
        .select_from(QuestionQualityReview)
        .join(Question, Question.id == QuestionQualityReview.question_id)
        .join(QuestionOutcomeMapping, QuestionOutcomeMapping.question_id == Question.id)
        .join(CurriculumOutcome, CurriculumOutcome.id == QuestionOutcomeMapping.outcome_id)
    )
    rows = result.fetchall()

    by_outcome: dict[str, dict] = {}
    for code, title, score in rows:
        if code not in by_outcome:
            by_outcome[code] = {"title": title, "scores": [], "total": 0}
        by_outcome[code]["scores"].append(score)
        by_outcome[code]["total"] += score

    results = []
    for code, data in sorted(by_outcome.items()):
        n = len(data["scores"])
        avg = round(data["total"] / n, 1) if n > 0 else 0
        needs_regen = sum(1 for s in data["scores"] if s < 3)

        # Also count published questions for this outcome
        count_result = await db.execute(
            select(func.count(Question.id))
            .select_from(CurriculumOutcome)
            .join(QuestionOutcomeMapping, QuestionOutcomeMapping.outcome_id == CurriculumOutcome.id)
            .join(Question, Question.id == QuestionOutcomeMapping.question_id)
            .where(CurriculumOutcome.code == code, Question.status == QuestionStatus.published)
        )
        published = count_result.scalar() or 0

        results.append({
            "outcome_code": code,
            "outcome_title": data["title"],
            "total_questions": published,
            "reviewed_count": n,
            "average_quality": avg,
            "needs_regeneration": needs_regen,
        })

    results.sort(key=lambda r: r["average_quality"])
    return results


# ── Regeneration Candidates ──────────────────────────────────────────────────


async def get_regeneration_candidates(db: AsyncSession, limit: int = 50) -> list[dict]:
    """Find questions with overall_score < 3 flagged for regeneration."""
    result = await db.execute(
        select(QuestionQualityReview, Question.source_type, Question.status)
        .join(Question, Question.id == QuestionQualityReview.question_id)
        .where(QuestionQualityReview.overall_score < 3)
        .order_by(QuestionQualityReview.overall_score)
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
