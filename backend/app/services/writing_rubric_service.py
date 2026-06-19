"""M5.2+M5.6 — Writing rubrics: templates, dimensions, versioning, reviewer scoring, views.

- Editing any rubric field or dimension creates a new immutable version.
- Published reviews are bound to a specific rubric version.
- Student/parent views render the versioned snapshot, never live rubric data.
"""
import logging
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.writing import (
    WritingReview,
    WritingReviewScore,
    WritingReviewStatus,
    WritingRubric,
    WritingRubricDimension,
    WritingRubricDimensionVersion,
    WritingRubricVersion,
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


def _dimversion_to_dict(dv: WritingRubricDimensionVersion) -> dict:
    return {
        "id": dv.id,
        "original_dimension_id": dv.original_dimension_id,
        "name": dv.name,
        "description": dv.description,
        "display_order": dv.display_order,
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
    result = await db.execute(
        select(WritingTask.rubric_id)
        .join(WritingSubmission, WritingSubmission.writing_task_id == WritingTask.id)
        .where(WritingSubmission.id == review.submission_id)
    )
    return result.scalar_one_or_none()


async def _next_version_number(rubric_id: str, db: AsyncSession) -> int:
    current_max = (await db.execute(
        select(func.max(WritingRubricVersion.version_number))
        .where(WritingRubricVersion.rubric_id == rubric_id)
    )).scalar()
    return (current_max or 0) + 1


async def _latest_version(rubric_id: str, db: AsyncSession) -> WritingRubricVersion | None:
    result = await db.execute(
        select(WritingRubricVersion)
        .where(WritingRubricVersion.rubric_id == rubric_id)
        .order_by(WritingRubricVersion.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── Version creation ─────────────────────────────────────────────────────────


async def _create_version_snapshot(
    rubric_id: str, actor_user_id: str | None, db: AsyncSession
) -> WritingRubricVersion:
    """Create an immutable snapshot of the rubric's current state. Returns the new version."""
    rubric = await _get_rubric(rubric_id, db)
    dimensions = await _dimensions_for_rubric(rubric_id, db)
    version_number = await _next_version_number(rubric_id, db)

    rv = WritingRubricVersion(
        rubric_id=rubric_id,
        version_number=version_number,
        title=rubric.title,
        active=rubric.active,
        created_by_admin_id=actor_user_id,
    )
    db.add(rv)
    await db.flush()

    for d in dimensions:
        db.add(WritingRubricDimensionVersion(
            rubric_version_id=rv.id,
            original_dimension_id=d.id,
            name=d.name,
            description=d.description,
            display_order=d.display_order,
        ))

    await audit_service.log_action(
        db,
        action="writing_rubric.version_created",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_rubric_version",
        target_id=rv.id,
        metadata={"rubric_id": rubric_id, "version_number": version_number},
    )
    await db.flush()
    return rv


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
    await db.flush()

    # Create version 1 snapshot.
    await _create_version_snapshot(rubric.id, actor_user_id, db)

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


async def get_rubric_versions(rubric_id: str, db: AsyncSession) -> list[dict]:
    """List all versions of a rubric (admin version history)."""
    result = await db.execute(
        select(WritingRubricVersion)
        .where(WritingRubricVersion.rubric_id == rubric_id)
        .order_by(WritingRubricVersion.version_number.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "title": v.title,
            "active": v.active,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


async def update_rubric(
    rubric_id: str, fields: dict, actor_user_id: str | None, db: AsyncSession
) -> dict:
    rubric = await _get_rubric(rubric_id, db)
    changed = False
    for key, value in fields.items():
        if value is not None and getattr(rubric, key) != value:
            setattr(rubric, key, value)
            changed = True

    if changed:
        await _create_version_snapshot(rubric_id, actor_user_id, db)

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
    await db.flush()
    await _create_version_snapshot(rubric_id, actor_user_id, db)

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

    changed = False
    previous = _dimension_to_dict(dimension)
    for key, value in fields.items():
        if value is not None and getattr(dimension, key) != value:
            setattr(dimension, key, value)
            changed = True

    if changed:
        await _create_version_snapshot(rubric_id, actor_user_id, db)

    await audit_service.log_action(
        db,
        action="writing_rubric.updated",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_rubric",
        target_id=rubric_id,
        metadata={
            "dimension_updated": dimension_id,
            "previous": {"name": previous["name"], "description": previous["description"], "display_order": previous["display_order"]},
            "new": {"name": dimension.name, "description": dimension.description, "display_order": dimension.display_order},
        },
    )
    await db.commit()
    await db.refresh(dimension)
    return _dimension_to_dict(dimension)


async def delete_dimension(
    rubric_id: str, dimension_id: str, actor_user_id: str | None, db: AsyncSession
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

    # Block if any published review already scores this dimension (via version snapshots).
    scored = (await db.execute(
        select(WritingReviewScore.id)
        .join(WritingRubricDimensionVersion,
              WritingRubricDimensionVersion.id == WritingReviewScore.dimension_version_id)
        .where(WritingRubricDimensionVersion.original_dimension_id == dimension_id)
        .limit(1)
    )).scalar_one_or_none()
    if not scored:
        # Also check legacy scores via dimension_id directly.
        scored = (await db.execute(
            select(WritingReviewScore.id)
            .where(WritingReviewScore.dimension_id == dimension_id)
            .limit(1)
        )).scalar_one_or_none()
    if scored:
        raise HTTPException(
            status_code=422, detail="Cannot delete a dimension that already has review scores"
        )

    deleted_info = _dimension_to_dict(dimension)
    await audit_service.log_action(
        db,
        action="writing_rubric.updated",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_rubric",
        target_id=rubric_id,
        metadata={
            "dimension_deleted": dimension_id,
            "deleted": {"name": deleted_info["name"], "display_order": deleted_info["display_order"]},
        },
    )
    await db.delete(dimension)
    await db.flush()

    # Create a new version snapshot without the deleted dimension.
    await _create_version_snapshot(rubric_id, actor_user_id, db)
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

    changing = rubric_id != task.rubric_id
    if changing:
        scored = (await db.execute(
            select(WritingReviewScore.id)
            .join(WritingReview, WritingReview.id == WritingReviewScore.review_id)
            .join(WritingSubmission, WritingSubmission.id == WritingReview.submission_id)
            .where(WritingSubmission.writing_task_id == task_id)
            .limit(1)
        )).scalar_one_or_none()
        if scored:
            raise HTTPException(
                status_code=422,
                detail="Cannot change the rubric: submissions under this task already have rubric scores",
            )

    if rubric_id is not None:
        rubric = await _get_rubric(rubric_id, db)
        if not rubric.active:
            raise HTTPException(status_code=422, detail="Cannot assign an inactive rubric")
        dimension_count = len(await _dimensions_for_rubric(rubric_id, db))
        if dimension_count == 0:
            raise HTTPException(
                status_code=422, detail="Cannot assign a rubric with no dimensions"
            )

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


# ── Version-aware dimension resolution ───────────────────────────────────────


async def _dimensions_for_review(review: WritingReview, db: AsyncSession) -> tuple[list[dict], str | None]:
    """Return (dimension_dicts, version_id) for a review.

    If the review has a rubric_version_id (published), return the versioned
    snapshot dimensions. Otherwise return live dimensions. Admin/reviewer
    always sees live dimensions for in-progress reviews; students/parents
    see the versioned snapshot.
    """
    rubric_id = await _review_task_rubric_id(review, db)
    if not rubric_id:
        return [], None

    if review.rubric_version_id:
        rv = (await db.execute(
            select(WritingRubricVersion)
            .options(selectinload(WritingRubricVersion.dimension_versions))
            .where(WritingRubricVersion.id == review.rubric_version_id)
        )).scalar_one_or_none()
        if rv:
            return (
                [
                    {
                        "id": dv.original_dimension_id,
                        "dimension_version_id": dv.id,
                        "name": dv.name,
                        "description": dv.description,
                        "display_order": dv.display_order,
                    }
                    for dv in rv.dimension_versions
                ],
                str(rv.id),
            )

    # Fallback: live dimensions (in-progress review, or legacy without version)
    dims = await _dimensions_for_rubric(rubric_id, db)
    return (
        [
            {"id": d.id, "dimension_version_id": None, "name": d.name,
             "description": d.description, "display_order": d.display_order}
            for d in dims
        ],
        None,
    )


# ── Reviewer scoring ─────────────────────────────────────────────────────────


async def upsert_scores(
    review_id: str, scores: list, admin_profile_id: str, actor_user_id: str | None, db: AsyncSession
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

    dimensions, version_id = await _dimensions_for_review(review, db)
    valid_dimension_ids = {d["id"] for d in dimensions}
    dim_by_id = {d["id"]: d for d in dimensions}

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
        dv_id = dim_by_id[item.dimension_id].get("dimension_version_id")
        if item.dimension_id in existing:
            existing[item.dimension_id].rating = item.rating
            existing[item.dimension_id].comment = item.comment
            existing[item.dimension_id].created_by_admin_id = admin_profile_id
            existing[item.dimension_id].source = "human"
            if dv_id:
                existing[item.dimension_id].dimension_version_id = dv_id
        else:
            db.add(WritingReviewScore(
                review_id=review_id,
                dimension_id=item.dimension_id,
                dimension_version_id=dv_id,
                rating=item.rating,
                comment=item.comment,
                created_by_admin_id=admin_profile_id,
                source="human",
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


# ── Publish gate ─────────────────────────────────────────────────────────────


async def assert_rubric_complete_for_publish(review: WritingReview, db: AsyncSession) -> None:
    rubric_id = await _review_task_rubric_id(review, db)
    if not rubric_id:
        return
    dimensions, _ = await _dimensions_for_review(review, db)
    scores = {
        s.dimension_id: s
        for s in (await db.execute(
            select(WritingReviewScore).where(WritingReviewScore.review_id == review.id)
        )).scalars().all()
    }
    for d in dimensions:
        score = scores.get(d["id"])
        if score is None or not (score.comment or "").strip():
            raise HTTPException(
                status_code=422,
                detail="Cannot publish: every rubric dimension must have a rating and comment",
            )


# ── Admin review detail: rubric block ────────────────────────────────────────


async def rubric_block_for_review(review: WritingReview, db: AsyncSession) -> dict | None:
    """Rubric + current scores for the admin review detail view.
    Uses version snapshot when available, live dimensions otherwise."""
    rubric_id = await _review_task_rubric_id(review, db)
    if not rubric_id:
        return None

    rubric = await _get_rubric(rubric_id, db)
    dimensions, rubric_version_id = await _dimensions_for_review(review, db)
    scores = {
        s.dimension_id: s
        for s in (await db.execute(
            select(WritingReviewScore).where(WritingReviewScore.review_id == review.id)
        )).scalars().all()
    }
    return {
        "rubric_id": rubric.id,
        "title": rubric.title,
        "rubric_version_id": rubric_version_id,
        "scores": [
            {
                "dimension_id": d["id"],
                "name": d["name"],
                "description": d["description"],
                "display_order": d["display_order"],
                "rating": scores[d["id"]].rating if d["id"] in scores else None,
                "comment": scores[d["id"]].comment if d["id"] in scores else None,
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

    # ALWAYS use the versioned snapshot for published reviews.
    dimensions, rubric_version_id = await _dimensions_for_review(review, db)
    rubric = await _get_rubric(rubric_id, db)

    # Use the version title if available, otherwise live title
    rubric_title = rubric.title
    if review.rubric_version_id:
        rv_result = await db.execute(
            select(WritingRubricVersion.title)
            .where(WritingRubricVersion.id == review.rubric_version_id)
        )
        version_title = rv_result.scalar_one_or_none()
        if version_title:
            rubric_title = version_title

    scores = {
        s.dimension_id: s
        for s in (await db.execute(
            select(WritingReviewScore).where(WritingReviewScore.review_id == review.id)
        )).scalars().all()
    }
    return {
        "submission_id": submission_id,
        "rubric_title": rubric_title,
        "rubric_version_id": rubric_version_id,
        "framework_id": rubric.framework_id,
        "scores": [
            {
                "dimension_id": d["id"],
                "name": d["name"],
                "description": d["description"],
                "display_order": d["display_order"],
                "rating": scores[d["id"]].rating if d["id"] in scores else None,
                "comment": scores[d["id"]].comment if d["id"] in scores else None,
            }
            for d in dimensions
        ],
        "disclaimer": DISCLAIMER,
    }
