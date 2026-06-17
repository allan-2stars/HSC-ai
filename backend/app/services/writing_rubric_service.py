"""M5.2 — Writing rubrics: templates, dimensions, reviewer scoring, student/parent view.

Scores are editable while the review is not published, then frozen (rejected) once
published. Visibility of the rubric assessment follows the M5.1 publish gate.
"""
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.writing import (
    WritingReview,
    WritingReviewScore,
    WritingReviewStatus,
    WritingRubric,
    WritingRubricDimension,
    WritingSubmission,
    WritingTask,
)
from app.services import audit_service
from app.services.writing_review_service import DISCLAIMER

logger = logging.getLogger("hsc-ai.writing-rubric")


# ── serialisers ──────────────────────────────────────────────────────────────


def _dimension_to_dict(d: WritingRubricDimension) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "display_order": d.display_order,
    }


def _rubric_to_dict(r: WritingRubric) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "framework_id": r.framework_id,
        "subject_id": r.subject_id,
        "exam_type_id": r.exam_type_id,
        "active": r.active,
        "dimensions": [_dimension_to_dict(d) for d in r.dimensions],
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ── internal helpers ─────────────────────────────────────────────────────────


async def _get_rubric(rubric_id: str, db: AsyncSession) -> WritingRubric:
    result = await db.execute(
        select(WritingRubric).where(WritingRubric.id == rubric_id)
    )
    rubric = result.scalar_one_or_none()
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return rubric


async def _load_rubric_dict(rubric_id: str, db: AsyncSession) -> dict:
    """Fetch a rubric with dimensions eagerly loaded, serialised to a dict."""
    result = await db.execute(
        select(WritingRubric)
        .options(selectinload(WritingRubric.dimensions))
        .where(WritingRubric.id == rubric_id)
    )
    rubric = result.scalar_one_or_none()
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return _rubric_to_dict(rubric)


async def _dimensions_for_rubric(rubric_id: str, db: AsyncSession) -> list[WritingRubricDimension]:
    result = await db.execute(
        select(WritingRubricDimension)
        .where(WritingRubricDimension.rubric_id == rubric_id)
        .order_by(WritingRubricDimension.display_order)
    )
    return list(result.scalars().all())


async def _review_task_rubric_id(review: WritingReview, db: AsyncSession) -> str | None:
    """The rubric id assigned to the task behind this review (or None)."""
    result = await db.execute(
        select(WritingTask.rubric_id)
        .join(WritingSubmission, WritingSubmission.writing_task_id == WritingTask.id)
        .where(WritingSubmission.id == review.submission_id)
    )
    return result.scalar_one_or_none()


# ── Rubric CRUD ──────────────────────────────────────────────────────────────


async def create_rubric(
    db: AsyncSession,
    *,
    title: str,
    framework_id: str | None,
    subject_id: str | None,
    exam_type_id: str | None,
    active: bool,
    dimensions: list | None,
    actor_user_id: str | None,
) -> dict:
    rubric = WritingRubric(
        title=title,
        framework_id=framework_id,
        subject_id=subject_id,
        exam_type_id=exam_type_id,
        active=active,
    )
    db.add(rubric)
    await db.flush()
    for d in dimensions or []:
        db.add(WritingRubricDimension(
            rubric_id=rubric.id,
            name=d.name,
            description=d.description,
            display_order=d.display_order,
        ))
    await audit_service.log_action(
        db,
        action="writing_rubric.created",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_rubric",
        target_id=rubric.id,
        metadata={"title": title},
    )
    await db.commit()
    return await _load_rubric_dict(rubric.id, db)


async def list_rubrics(
    db: AsyncSession, active: bool | None = None, framework_id: str | None = None
) -> list[dict]:
    stmt = (
        select(WritingRubric)
        .options(selectinload(WritingRubric.dimensions))
        .order_by(WritingRubric.created_at.desc())
    )
    if active is not None:
        stmt = stmt.where(WritingRubric.active == active)
    if framework_id:
        stmt = stmt.where(WritingRubric.framework_id == framework_id)
    rubrics = (await db.execute(stmt)).scalars().all()
    return [_rubric_to_dict(r) for r in rubrics]


async def get_rubric(rubric_id: str, db: AsyncSession) -> dict:
    return await _load_rubric_dict(rubric_id, db)


async def update_rubric(
    rubric_id: str, fields: dict, actor_user_id: str | None, db: AsyncSession
) -> dict:
    rubric = await _get_rubric(rubric_id, db)
    for key, value in fields.items():
        if value is not None:
            setattr(rubric, key, value)
    await audit_service.log_action(
        db,
        action="writing_rubric.updated",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_rubric",
        target_id=rubric.id,
    )
    await db.commit()
    return await _load_rubric_dict(rubric.id, db)


# ── Dimension management ─────────────────────────────────────────────────────


async def add_dimension(
    rubric_id: str, name: str, description: str | None, display_order: int,
    actor_user_id: str | None, db: AsyncSession,
) -> dict:
    await _get_rubric(rubric_id, db)
    dimension = WritingRubricDimension(
        rubric_id=rubric_id, name=name, description=description, display_order=display_order
    )
    db.add(dimension)
    await audit_service.log_action(
        db,
        action="writing_rubric.updated",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_rubric",
        target_id=rubric_id,
        metadata={"dimension_added": name},
    )
    await db.commit()
    await db.refresh(dimension)
    return _dimension_to_dict(dimension)


async def update_dimension(
    rubric_id: str, dimension_id: str, fields: dict,
    actor_user_id: str | None, db: AsyncSession,
) -> dict:
    result = await db.execute(
        select(WritingRubricDimension).where(
            WritingRubricDimension.id == dimension_id,
            WritingRubricDimension.rubric_id == rubric_id,
        )
    )
    dimension = result.scalar_one_or_none()
    if not dimension:
        raise HTTPException(status_code=404, detail="Dimension not found")
    for key, value in fields.items():
        if value is not None:
            setattr(dimension, key, value)
    await db.commit()
    await db.refresh(dimension)
    return _dimension_to_dict(dimension)


async def delete_dimension(
    rubric_id: str, dimension_id: str, db: AsyncSession
) -> None:
    result = await db.execute(
        select(WritingRubricDimension).where(
            WritingRubricDimension.id == dimension_id,
            WritingRubricDimension.rubric_id == rubric_id,
        )
    )
    dimension = result.scalar_one_or_none()
    if not dimension:
        raise HTTPException(status_code=404, detail="Dimension not found")
    # Block deletion if any review has already scored this dimension.
    scored = (await db.execute(
        select(WritingReviewScore.id).where(WritingReviewScore.dimension_id == dimension_id).limit(1)
    )).scalar_one_or_none()
    if scored:
        raise HTTPException(
            status_code=422, detail="Cannot delete a dimension that already has review scores"
        )
    await db.delete(dimension)
    await db.commit()


# ── Assign rubric to task ────────────────────────────────────────────────────


async def assign_rubric_to_task(
    task_id: str, rubric_id: str | None, actor_user_id: str | None, db: AsyncSession
) -> dict:
    task = (await db.execute(
        select(WritingTask).where(WritingTask.id == task_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Writing task not found")
    if rubric_id is not None:
        await _get_rubric(rubric_id, db)  # validate existence
    task.rubric_id = rubric_id
    await audit_service.log_action(
        db,
        action="writing_task.rubric_assigned",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_task",
        target_id=task_id,
        metadata={"rubric_id": rubric_id},
    )
    await db.commit()
    return {"task_id": task_id, "rubric_id": rubric_id}


# ── Reviewer scoring ─────────────────────────────────────────────────────────


async def upsert_scores(
    review_id: str, scores: list, actor_user_id: str | None, db: AsyncSession
) -> dict:
    review = (await db.execute(
        select(WritingReview).where(WritingReview.id == review_id)
    )).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status == WritingReviewStatus.published:
        raise HTTPException(status_code=422, detail="Cannot edit scores after publishing")

    rubric_id = await _review_task_rubric_id(review, db)
    if not rubric_id:
        raise HTTPException(status_code=422, detail="No rubric is assigned to this task")

    valid_dimension_ids = {d.id for d in await _dimensions_for_rubric(rubric_id, db)}

    existing = {
        s.dimension_id: s
        for s in (await db.execute(
            select(WritingReviewScore).where(WritingReviewScore.review_id == review_id)
        )).scalars().all()
    }

    for item in scores:
        if item.dimension_id not in valid_dimension_ids:
            raise HTTPException(
                status_code=422,
                detail="Dimension does not belong to the rubric assigned to this task",
            )
        if item.dimension_id in existing:
            existing[item.dimension_id].rating = item.rating
            existing[item.dimension_id].comment = item.comment
        else:
            db.add(WritingReviewScore(
                review_id=review_id,
                dimension_id=item.dimension_id,
                rating=item.rating,
                comment=item.comment,
            ))

    await audit_service.log_action(
        db,
        action="writing_review.scored",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review",
        target_id=review_id,
        metadata={"dimension_count": len(scores)},
    )
    await db.commit()

    rows = (await db.execute(
        select(WritingReviewScore).where(WritingReviewScore.review_id == review_id)
    )).scalars().all()
    return {
        "review_id": review_id,
        "scores": [
            {"dimension_id": s.dimension_id, "rating": s.rating, "comment": s.comment}
            for s in rows
        ],
    }


# ── Publish gate (called from the review publish flow) ───────────────────────


async def assert_rubric_complete_for_publish(review: WritingReview, db: AsyncSession) -> None:
    """If the task has an assigned rubric, every dimension must have a score with
    a rating and a non-empty comment. No-op when no rubric is assigned."""
    rubric_id = await _review_task_rubric_id(review, db)
    if not rubric_id:
        return
    dimensions = await _dimensions_for_rubric(rubric_id, db)
    scores = {
        s.dimension_id: s
        for s in (await db.execute(
            select(WritingReviewScore).where(WritingReviewScore.review_id == review.id)
        )).scalars().all()
    }
    for d in dimensions:
        score = scores.get(d.id)
        if score is None or not (score.comment or "").strip():
            raise HTTPException(
                status_code=422,
                detail="Cannot publish: every rubric dimension must have a rating and comment",
            )


# ── Admin review detail: rubric block ────────────────────────────────────────


async def rubric_block_for_review(review: WritingReview, db: AsyncSession) -> dict | None:
    """Rubric + current scores for the admin review detail view, or None if the
    task has no rubric assigned."""
    rubric_id = await _review_task_rubric_id(review, db)
    if not rubric_id:
        return None
    rubric = await _get_rubric(rubric_id, db)
    dimensions = await _dimensions_for_rubric(rubric_id, db)
    scores = {
        s.dimension_id: s
        for s in (await db.execute(
            select(WritingReviewScore).where(WritingReviewScore.review_id == review.id)
        )).scalars().all()
    }
    return {
        "rubric_id": rubric.id,
        "title": rubric.title,
        "scores": [
            {
                "dimension_id": d.id,
                "name": d.name,
                "description": d.description,
                "display_order": d.display_order,
                "rating": scores[d.id].rating if d.id in scores else None,
                "comment": scores[d.id].comment if d.id in scores else None,
            }
            for d in dimensions
        ],
    }


# ── Student / parent: published rubric assessment ────────────────────────────


async def get_published_rubric_for_submission(submission_id: str, db: AsyncSession) -> dict:
    review = (await db.execute(
        select(WritingReview).where(WritingReview.submission_id == submission_id)
    )).scalar_one_or_none()
    if not review or review.status != WritingReviewStatus.published:
        raise HTTPException(status_code=404, detail="No published rubric assessment")

    rubric_id = await _review_task_rubric_id(review, db)
    if not rubric_id:
        raise HTTPException(status_code=404, detail="No rubric assessment for this submission")

    rubric = await _get_rubric(rubric_id, db)
    dimensions = await _dimensions_for_rubric(rubric_id, db)
    scores = {
        s.dimension_id: s
        for s in (await db.execute(
            select(WritingReviewScore).where(WritingReviewScore.review_id == review.id)
        )).scalars().all()
    }
    return {
        "submission_id": submission_id,
        "rubric_title": rubric.title,
        "framework_id": rubric.framework_id,
        "scores": [
            {
                "dimension_id": d.id,
                "name": d.name,
                "description": d.description,
                "display_order": d.display_order,
                "rating": scores[d.id].rating if d.id in scores else None,
                "comment": scores[d.id].comment if d.id in scores else None,
            }
            for d in dimensions
        ],
        "disclaimer": DISCLAIMER,
    }
