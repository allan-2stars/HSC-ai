"""M5.4 — AI score suggestion orchestration: generate, list, apply, dismiss.

- Generate: builds context from review + rubric version, calls provider, creates rows.
- List: returns current suggestions for a review.
- Apply: writes through existing human scoring path (upsert_scores). Never auto-publishes.
- Dismiss: marks dismissed. Never deletes.

Strictly admin-only. Never visible to students/parents.
"""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.writing import (
    WritingReview,
    WritingReviewStatus,
    WritingRubricDimensionVersion,
    WritingRubricVersion,
    WritingScoreSuggestion,
    WritingScoreSuggestionStatus,
    WritingSubmission,
    WritingTask,
)
from app.services import audit_service
from app.services.writing_score_suggestion_provider import (
    PROMPT_VERSION,
    ScoreSuggestionParams,
    generate_score_suggestions,
)

logger = logging.getLogger("hsc-ai.score-suggestion")


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _get_review(review_id: str, db: AsyncSession) -> WritingReview:
    result = await db.execute(select(WritingReview).where(WritingReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


async def _get_suggestion(suggestion_id: str, db: AsyncSession) -> WritingScoreSuggestion:
    result = await db.execute(select(WritingScoreSuggestion).where(WritingScoreSuggestion.id == suggestion_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Score suggestion not found")
    return s


async def _build_params(review: WritingReview, db: AsyncSession) -> ScoreSuggestionParams:
    """Build provider input from review context — no student PII."""
    row = (await db.execute(
        select(WritingSubmission, WritingTask.title, WritingTask.prompt, WritingTask.instructions, WritingTask.rubric_id)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .where(WritingSubmission.id == review.submission_id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    submission, task_title, task_prompt, task_instructions, task_rubric_id = row

    # Use rubric version snapshot if available, otherwise load latest version
    rubric_version: WritingRubricVersion | None = None
    if review.rubric_version_id:
        rv_result = await db.execute(
            select(WritingRubricVersion)
            .options(selectinload(WritingRubricVersion.dimension_versions))
            .where(WritingRubricVersion.id == review.rubric_version_id)
        )
        rubric_version = rv_result.scalar_one_or_none()

    # Fallback: load latest version from the task's rubric (before publish)
    if not rubric_version and task_rubric_id:
        from app.services.writing_rubric_service import _latest_version
        rubric_version = await _latest_version(task_rubric_id, db)
        if rubric_version:
            # Eager-load dimensions
            rv_result = await db.execute(
                select(WritingRubricVersion)
                .options(selectinload(WritingRubricVersion.dimension_versions))
                .where(WritingRubricVersion.id == rubric_version.id)
            )
            rubric_version = rv_result.scalar_one_or_none()

    rubric_title = "No rubric"
    dimension_versions = []
    if rubric_version:
        rubric_title = rubric_version.title
        dimension_versions = [
            {"id": dv.id, "name": dv.name, "description": dv.description, "display_order": dv.display_order}
            for dv in rubric_version.dimension_versions
        ]

    return ScoreSuggestionParams(
        task_title=task_title,
        task_prompt=task_prompt,
        task_instructions=task_instructions or "",
        submission_content=submission.content,
        word_count=submission.word_count,
        rubric_title=rubric_title,
        dimension_versions=dimension_versions,
    )


# ── Generate ────────────────────────────────────────────────────────────────


async def generate_suggestions(
    review_id: str,
    admin_profile_id: str,
    actor_user_id: str | None,
    provider_name: str = "mock",
    db: AsyncSession = None,
) -> list[dict]:
    review = await _get_review(review_id, db)
    if review.status == WritingReviewStatus.published:
        raise HTTPException(status_code=422, detail="Cannot generate suggestions for a published review")

    params = await _build_params(review, db)
    if not params.dimension_versions:
        raise HTTPException(status_code=422, detail="No rubric dimensions available for this review")

    # Use the version we loaded (could be from review or latest from task)
    rubric_version_id = review.rubric_version_id
    if not rubric_version_id:
        from app.services.writing_rubric_service import _review_task_rubric_id, _latest_version
        task_rubric_id = await _review_task_rubric_id(review, db)
        if task_rubric_id:
            latest = await _latest_version(task_rubric_id, db)
            if latest:
                rubric_version_id = latest.id
    if not rubric_version_id:
        raise HTTPException(status_code=422, detail="Review has no rubric version assigned")

    result = await generate_score_suggestions(params, provider_name)

    suggestions = []
    for item in result.dimension_suggestions:
        dv_id = item.get("dimension_version_id", "")
        rating = item.get("suggested_rating")
        if rating is not None and rating not in range(1, 6):
            raise HTTPException(status_code=422, detail=f"Invalid suggested rating: {rating}")
        s = WritingScoreSuggestion(
            review_id=review_id,
            rubric_version_id=rubric_version_id,
            dimension_version_id=dv_id,
            suggested_rating=rating,
            suggested_comment=item.get("suggested_comment", ""),
            confidence=item.get("confidence"),
            provider=result.provider,
            model=result.model,
            prompt_version=PROMPT_VERSION,
            status=WritingScoreSuggestionStatus.generated,
            generated_by_admin_id=admin_profile_id,
        )
        db.add(s)
        await db.flush()
        suggestions.append(s)

    await audit_service.log_action(
        db,
        action="writing_score_suggestion.generated",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review",
        target_id=review_id,
        metadata={
            "provider": result.provider,
            "model": result.model,
            "suggestion_count": len(suggestions),
        },
    )
    await db.commit()

    # Re-fetch with dimension names
    return await _list_suggestions(review_id, db)


async def _list_suggestions(review_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(WritingScoreSuggestion, WritingRubricDimensionVersion.name)
        .join(WritingRubricDimensionVersion,
              WritingRubricDimensionVersion.id == WritingScoreSuggestion.dimension_version_id)
        .where(WritingScoreSuggestion.review_id == review_id)
        .order_by(WritingScoreSuggestion.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": s.id,
            "review_id": s.review_id,
            "dimension_version_id": s.dimension_version_id,
            "dimension_name": dim_name,
            "suggested_rating": s.suggested_rating,
            "suggested_comment": s.suggested_comment,
            "confidence": s.confidence,
            "provider": s.provider,
            "status": s.status.value,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s, dim_name in rows
    ]


# ── List ────────────────────────────────────────────────────────────────────


async def list_suggestions(review_id: str, db: AsyncSession) -> list[dict]:
    await _get_review(review_id, db)
    return await _list_suggestions(review_id, db)


# ── Apply ───────────────────────────────────────────────────────────────────


async def apply_suggestion(
    suggestion_id: str,
    admin_profile_id: str,
    actor_user_id: str | None,
    db: AsyncSession,
) -> dict:
    s = await _get_suggestion(suggestion_id, db)
    if s.status != WritingScoreSuggestionStatus.generated:
        raise HTTPException(status_code=422, detail="Suggestion is not in generated state")

    review = await _get_review(s.review_id, db)
    if review.status == WritingReviewStatus.published:
        raise HTTPException(status_code=422, detail="Cannot apply — review is already published")

    # Resolve the live dimension_id from the version (needed by upsert_scores).
    dv_result = await db.execute(
        select(WritingRubricDimensionVersion.original_dimension_id)
        .where(WritingRubricDimensionVersion.id == s.dimension_version_id)
    )
    dim_row = dv_result.fetchone()
    if not dim_row or not dim_row[0]:
        raise HTTPException(status_code=422, detail="Dimension version has no original dimension")
    dimension_id = dim_row[0]

    from app.services import writing_rubric_service
    from app.schemas.writing_schema import ReviewScoreInput

    score_input = ReviewScoreInput(
        dimension_id=dimension_id,
        rating=s.suggested_rating or 3,
        comment=s.suggested_comment or "",
    )
    await writing_rubric_service.upsert_scores(
        review_id=s.review_id,
        scores=[score_input],
        admin_profile_id=admin_profile_id,
        actor_user_id=actor_user_id,
        db=db,
    )

    s.status = WritingScoreSuggestionStatus.applied
    await audit_service.log_action(
        db,
        action="writing_score_suggestion.applied",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_score_suggestion",
        target_id=suggestion_id,
        metadata={"review_id": s.review_id, "dimension_version_id": s.dimension_version_id},
    )
    await db.commit()
    await db.refresh(s)

    return {
        "id": s.id,
        "status": s.status.value,
        "review_id": s.review_id,
    }


# ── Dismiss ─────────────────────────────────────────────────────────────────


async def dismiss_suggestion(
    suggestion_id: str,
    actor_user_id: str | None,
    db: AsyncSession,
) -> dict:
    s = await _get_suggestion(suggestion_id, db)
    if s.status != WritingScoreSuggestionStatus.generated:
        raise HTTPException(status_code=422, detail="Suggestion is not in generated state")

    s.status = WritingScoreSuggestionStatus.dismissed
    await audit_service.log_action(
        db,
        action="writing_score_suggestion.dismissed",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_score_suggestion",
        target_id=suggestion_id,
        metadata={"review_id": s.review_id},
    )
    await db.commit()
    await db.refresh(s)

    return {
        "id": s.id,
        "status": s.status.value,
        "review_id": s.review_id,
    }
