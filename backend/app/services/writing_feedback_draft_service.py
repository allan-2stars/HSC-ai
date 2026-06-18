"""M5.3 — AI feedback drafts.

Generates AI **draft** feedback for a writing review. Drafts are admin/reviewer-only
and are never exposed to students or parents. None of these operations assign rubric
scores, edit ratings, publish a review, or overwrite official feedback on their own —
copying a draft into official feedback happens only via the explicit human ``accept``
action, which routes through the normal versioned-feedback path.
"""
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.writing import (
    WritingFeedbackDraft,
    WritingFeedbackDraftStatus,
    WritingReview,
    WritingReviewStatus,
    WritingSubmission,
    WritingTask,
)
from app.services import audit_service, writing_review_service
from app.services.writing_feedback_providers import (
    PROMPT_VERSION,
    FeedbackParams,
    get_feedback_provider,
)
from app.services.writing_rubric_service import (
    _dimensions_for_rubric,
    _review_task_rubric_id,
)

logger = logging.getLogger("hsc-ai.writing-feedback-draft")


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _get_review(review_id: str, db: AsyncSession) -> WritingReview:
    review = (await db.execute(
        select(WritingReview).where(WritingReview.id == review_id)
    )).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


async def _get_draft(draft_id: str, db: AsyncSession) -> WritingFeedbackDraft:
    draft = (await db.execute(
        select(WritingFeedbackDraft).where(WritingFeedbackDraft.id == draft_id)
    )).scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


def _draft_to_dict(d: WritingFeedbackDraft) -> dict:
    return {
        "id": d.id,
        "review_id": d.review_id,
        "provider": d.provider,
        "model": d.model,
        "prompt_version": d.prompt_version,
        "status": d.status,
        "draft_feedback": d.draft_feedback_json,
        "generated_by_admin_id": d.generated_by_admin_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def _compose_overall_comment(fb: dict) -> str:
    """Flatten a structured draft into a single overall_comment for official feedback.
    The reviewer can freely edit this afterwards."""
    parts: list[str] = []
    overall = (fb.get("overall_feedback") or "").strip()
    if overall:
        parts.append(overall)

    def _section(title: str, items) -> None:
        cleaned = [str(i).strip() for i in (items or []) if str(i).strip()]
        if cleaned:
            parts.append(title + "\n" + "\n".join(f"- {i}" for i in cleaned))

    _section("Strengths:", fb.get("strengths"))
    _section("Areas for improvement:", fb.get("improvements"))
    _section("Next steps:", fb.get("next_steps"))
    return "\n\n".join(parts) if parts else "(AI draft accepted — please edit.)"


# ── Generate ─────────────────────────────────────────────────────────────────


async def generate_ai_feedback_draft(
    review_id: str,
    *,
    admin_profile_id: str,
    actor_user_id: str | None,
    provider_name: str | None,
    db: AsyncSession,
) -> dict:
    """Generate a new AI draft for the review. Does not touch official feedback,
    rubric scores, or publish state."""
    review = await _get_review(review_id, db)
    if review.status == WritingReviewStatus.published:
        raise HTTPException(
            status_code=422, detail="Cannot generate an AI draft for a published review"
        )

    row = (await db.execute(
        select(WritingSubmission, WritingTask)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .where(WritingSubmission.id == review.submission_id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    submission, task = row

    # Rubric dimension labels (if any) — never any student PII.
    rubric_dimensions: list[dict] = []
    rubric_id = await _review_task_rubric_id(review, db)
    if rubric_id:
        rubric_dimensions = [
            {"name": d.name, "description": d.description}
            for d in await _dimensions_for_rubric(rubric_id, db)
        ]

    params = FeedbackParams(
        task_title=task.title,
        task_prompt=task.prompt,
        task_instructions=task.instructions or "",
        submission_content=submission.content,
        word_count=submission.word_count,
        rubric_dimensions=rubric_dimensions,
    )

    provider = get_feedback_provider(provider_name)
    try:
        result = await provider(params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"AI provider error: {e}")
    except HTTPException:
        raise
    except Exception as e:  # network / upstream failure
        logger.warning("AI feedback draft generation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI provider error: {e}")

    draft = WritingFeedbackDraft(
        review_id=review.id,
        provider=result.provider,
        model=result.model,
        prompt_version=PROMPT_VERSION,
        status=WritingFeedbackDraftStatus.generated.value,
        draft_feedback_json={
            "strengths": result.strengths,
            "improvements": result.improvements,
            "next_steps": result.next_steps,
            "overall_feedback": result.overall_feedback,
        },
        generated_by_admin_id=admin_profile_id,
    )
    db.add(draft)
    await db.flush()
    await audit_service.log_action(
        db,
        action="writing_feedback_draft.generated",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review",
        target_id=review.id,
        metadata={"draft_id": draft.id, "provider": result.provider},
    )
    await db.commit()
    await db.refresh(draft)
    return _draft_to_dict(draft)


# ── List ─────────────────────────────────────────────────────────────────────


async def list_drafts_for_review(review_id: str, db: AsyncSession) -> list[dict]:
    await _get_review(review_id, db)
    rows = (await db.execute(
        select(WritingFeedbackDraft)
        .where(WritingFeedbackDraft.review_id == review_id)
        .order_by(WritingFeedbackDraft.created_at.desc())
    )).scalars().all()
    return [_draft_to_dict(d) for d in rows]


# ── Discard ──────────────────────────────────────────────────────────────────


async def discard_draft(
    draft_id: str, *, actor_user_id: str | None, db: AsyncSession
) -> dict:
    draft = await _get_draft(draft_id, db)
    draft.status = WritingFeedbackDraftStatus.discarded.value
    await audit_service.log_action(
        db,
        action="writing_feedback_draft.discarded",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_feedback_draft",
        target_id=draft.id,
        metadata={"review_id": draft.review_id},
    )
    await db.commit()
    await db.refresh(draft)
    return _draft_to_dict(draft)


# ── Accept (copy into official feedback — explicit human action) ──────────────


async def accept_draft(
    draft_id: str,
    *,
    admin_profile_id: str,
    actor_user_id: str | None,
    db: AsyncSession,
) -> dict:
    """Copy a draft into official (versioned) feedback. This is a deliberate human
    action: it adds a new feedback version via the normal review path (which the
    reviewer can later edit), and marks the draft accepted. It never publishes."""
    draft = await _get_draft(draft_id, db)
    if draft.status == WritingFeedbackDraftStatus.discarded.value:
        raise HTTPException(status_code=422, detail="Cannot accept a discarded draft")

    overall_comment = _compose_overall_comment(draft.draft_feedback_json)
    # add_feedback commits and enforces the "no edits after publish" guard.
    result = await writing_review_service.add_feedback(
        draft.review_id,
        overall_comment=overall_comment,
        dimensions=None,
        admin_profile_id=admin_profile_id,
        actor_user_id=actor_user_id,
        db=db,
    )

    draft.status = WritingFeedbackDraftStatus.accepted.value
    await audit_service.log_action(
        db,
        action="writing_feedback_draft.accepted",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_feedback_draft",
        target_id=draft.id,
        metadata={"review_id": draft.review_id},
    )
    await db.commit()
    return result
