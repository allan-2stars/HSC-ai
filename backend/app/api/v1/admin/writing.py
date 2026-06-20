from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin_profile
from app.models.user import AdminProfile
from app.models.writing import WritingTaskStatus
from app.schemas.writing_schema import (
    AIDraftGenerate,
    AdminReviewNote,
    ReviewScoresCreate,
    RubricAssign,
    RubricCreate,
    RubricDimensionInput,
    RubricDimensionUpdate,
    RubricUpdate,
    ScoreSuggestionGenerateRequest,
    WritingFeedbackCreate,
    WritingSubmissionListItem,
    WritingTaskCreate,
    WritingTaskResponse,
)
from app.services import (
    writing_analytics_service,
    writing_dispute_service,
    writing_feedback_draft_service,
    writing_portfolio_service,
    writing_review_service,
    writing_rubric_service,
    writing_score_suggestion_service,
    writing_service,
)

router = APIRouter(prefix="/admin/writing", tags=["admin-writing"])


# ── Tasks ──────────────────────────────────────────────────────────────────


@router.post("/tasks", response_model=WritingTaskResponse, status_code=201)
async def create_writing_task(
    body: WritingTaskCreate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    task = await writing_service.create_writing_task(
        db=db,
        title=body.title,
        prompt=body.prompt,
        instructions=body.instructions,
        word_limit=body.word_limit,
        recommended_time_minutes=body.recommended_time_minutes,
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
        admin_profile_id=admin_profile.id,
    )
    return _task_to_response(task)


@router.get("/tasks", response_model=list[WritingTaskResponse])
async def list_writing_tasks(
    status: str | None = None,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    tasks = await writing_service.list_writing_tasks(db, status_str=status)
    return [_task_to_response(t) for t in tasks]


@router.patch("/tasks/{task_id}/publish", response_model=WritingTaskResponse)
async def publish_writing_task(
    task_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    task = await writing_service.update_writing_task_status(
        task_id, WritingTaskStatus.published, db
    )
    return _task_to_response(task)


@router.patch("/tasks/{task_id}/archive", response_model=WritingTaskResponse)
async def archive_writing_task(
    task_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    task = await writing_service.update_writing_task_status(
        task_id, WritingTaskStatus.archived, db
    )
    return _task_to_response(task)


# ── Submissions (review) ───────────────────────────────────────────────────


@router.get("/submissions", response_model=list[WritingSubmissionListItem])
async def list_all_submissions(
    task_id: str | None = None,
    status: str | None = None,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_service.list_all_submissions(
        db, task_id=task_id, status_str=status
    )


# ── Human review workflow (M5.1) ────────────────────────────────────────────


@router.get("/reviews")
async def list_reviews(
    status: str | None = None,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_review_service.list_reviews(db, status_str=status)


@router.get("/reviews/{review_id}")
async def get_review(
    review_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_review_service.get_review_detail(
        review_id, actor_user_id=admin_profile.user_id, db=db
    )


@router.post("/reviews/{review_id}/assign")
async def assign_review(
    review_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    # Self-assignment for V1 (reviewer balancing is out of scope).
    return await writing_review_service.assign_review(
        review_id,
        reviewer_admin_id=admin_profile.id,
        actor_user_id=admin_profile.user_id,
        db=db,
    )


@router.post("/reviews/{review_id}/feedback")
async def add_feedback(
    review_id: str,
    body: WritingFeedbackCreate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_review_service.add_feedback(
        review_id,
        overall_comment=body.overall_comment,
        dimensions=body.dimensions,
        admin_profile_id=admin_profile.id,
        actor_user_id=admin_profile.user_id,
        db=db,
    )


@router.post("/reviews/{review_id}/publish")
async def publish_review(
    review_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_review_service.publish_review(
        review_id, actor_user_id=admin_profile.user_id, db=db
    )


# ── Rubrics (M5.2) ──────────────────────────────────────────────────────────


@router.post("/rubrics", status_code=201)
async def create_rubric(
    body: RubricCreate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.create_rubric(
        db,
        title=body.title,
        framework_id=body.framework_id,
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
        active=body.active,
        dimensions=body.dimensions,
        actor_user_id=admin_profile.user_id,
    )


@router.get("/rubrics")
async def list_rubrics(
    active: bool | None = None,
    framework_id: str | None = None,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.list_rubrics(db, active=active, framework_id=framework_id)


@router.get("/rubrics/{rubric_id}")
async def get_rubric(
    rubric_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.get_rubric(rubric_id, db)


@router.patch("/rubrics/{rubric_id}")
async def update_rubric(
    rubric_id: str,
    body: RubricUpdate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.update_rubric(
        rubric_id, body.model_dump(exclude_unset=True), admin_profile.user_id, db
    )


@router.get("/rubrics/{rubric_id}/versions")
async def list_rubric_versions(
    rubric_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.get_rubric_versions(rubric_id, db)


@router.post("/rubrics/{rubric_id}/dimensions", status_code=201)
async def add_dimension(
    rubric_id: str,
    body: RubricDimensionInput,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.add_dimension(
        rubric_id, body.name, body.description, body.display_order, admin_profile.user_id, db
    )


@router.patch("/rubrics/{rubric_id}/dimensions/{dimension_id}")
async def update_dimension(
    rubric_id: str,
    dimension_id: str,
    body: RubricDimensionUpdate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.update_dimension(
        rubric_id, dimension_id, body.model_dump(exclude_unset=True), admin_profile.user_id, db
    )


@router.delete("/rubrics/{rubric_id}/dimensions/{dimension_id}", status_code=204)
async def delete_dimension(
    rubric_id: str,
    dimension_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    await writing_rubric_service.delete_dimension(
        rubric_id, dimension_id, admin_profile.user_id, db
    )


@router.post("/tasks/{task_id}/rubric")
async def assign_rubric(
    task_id: str,
    body: RubricAssign,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.assign_rubric_to_task(
        task_id, body.rubric_id, admin_profile.user_id, db
    )


@router.post("/reviews/{review_id}/scores")
async def score_review(
    review_id: str,
    body: ReviewScoresCreate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_rubric_service.upsert_scores(
        review_id, body.scores, admin_profile.id, admin_profile.user_id, db
    )


# ── AI feedback drafts (M5.3) ────────────────────────────────────────────────


@router.post("/reviews/{review_id}/ai-draft", status_code=201)
async def generate_ai_draft(
    review_id: str,
    body: AIDraftGenerate,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_feedback_draft_service.generate_ai_feedback_draft(
        review_id,
        admin_profile_id=admin_profile.id,
        actor_user_id=admin_profile.user_id,
        provider_name=body.provider,
        db=db,
    )


@router.get("/reviews/{review_id}/ai-drafts")
async def list_ai_drafts(
    review_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_feedback_draft_service.list_drafts_for_review(review_id, db)


@router.post("/ai-drafts/{draft_id}/accept")
async def accept_ai_draft(
    draft_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_feedback_draft_service.accept_draft(
        draft_id,
        admin_profile_id=admin_profile.id,
        actor_user_id=admin_profile.user_id,
        db=db,
    )


@router.post("/ai-drafts/{draft_id}/discard")
async def discard_ai_draft(
    draft_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_feedback_draft_service.discard_draft(
        draft_id, actor_user_id=admin_profile.user_id, db=db
    )


# ── AI score suggestions (M5.4) ────────────────────────────────────────────────


@router.post("/reviews/{review_id}/score-suggestions", status_code=201)
async def generate_score_suggestions(
    review_id: str,
    body: ScoreSuggestionGenerateRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_score_suggestion_service.generate_suggestions(
        review_id,
        admin_profile_id=admin_profile.id,
        actor_user_id=admin_profile.user_id,
        provider_name=body.provider or "mock",
        db=db,
    )


@router.get("/reviews/{review_id}/score-suggestions")
async def list_score_suggestions(
    review_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_score_suggestion_service.list_suggestions(review_id, db)


@router.post("/score-suggestions/{suggestion_id}/apply")
async def apply_score_suggestion(
    suggestion_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_score_suggestion_service.apply_suggestion(
        suggestion_id,
        admin_profile_id=admin_profile.id,
        actor_user_id=admin_profile.user_id,
        db=db,
    )


@router.post("/score-suggestions/{suggestion_id}/dismiss")
async def dismiss_score_suggestion(
    suggestion_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_score_suggestion_service.dismiss_suggestion(
        suggestion_id,
        actor_user_id=admin_profile.user_id,
        db=db,
    )


# ── Disputes & Reopen (M5.5) ────────────────────────────────────────────────


@router.get("/disputes")
async def list_disputes(
    status: str | None = None,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_dispute_service.list_all_disputes(db, status_str=status)


@router.post("/disputes/{dispute_id}/accept")
async def accept_dispute(
    dispute_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_dispute_service.accept_dispute(
        dispute_id, admin_profile.id, admin_profile.user_id, db
    )


@router.post("/disputes/{dispute_id}/reject")
async def reject_dispute(
    dispute_id: str,
    body: AdminReviewNote,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_dispute_service.reject_dispute(
        dispute_id, admin_profile.id, body.review_notes, admin_profile.user_id, db
    )


@router.post("/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_dispute_service.resolve_dispute(
        dispute_id, admin_profile.id, admin_profile.user_id, db
    )


@router.post("/reviews/{review_id}/reopen")
async def reopen_review(
    review_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_dispute_service.reopen_review(
        review_id, admin_profile.user_id, db
    )


@router.post("/reviews/{review_id}/republish")
async def republish_review(
    review_id: str,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_dispute_service.republish_review(
        review_id, admin_profile.user_id, admin_profile.id, db
    )


@router.get("/reviews/{review_id}/publication-versions")
async def list_publication_versions(
    review_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_dispute_service.list_publication_versions(review_id, db)


@router.get("/publication-versions/{version_id}")
async def get_publication_version(
    version_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_dispute_service.get_publication_version_detail(version_id, db)


# ── Writing Analytics (M5.7) ──────────────────────────────────────────────


@router.get("/analytics/overview")
async def admin_analytics_overview(
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_analytics_service.build_admin_overview(db)


@router.get("/analytics/students/{student_id}")
async def admin_student_analytics(
    student_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_analytics_service.build_student_analytics(student_id, db)


# ── Portfolio (M5.8) ──────────────────────────────────────────────────────


@router.get("/portfolio/students/{student_id}")
async def admin_student_portfolio(
    student_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_portfolio_service.build_portfolio_list(student_id, db)


@router.get("/portfolio/students/{student_id}/items/{submission_id}")
async def admin_student_portfolio_item(
    student_id: str,
    submission_id: str,
    _: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await writing_portfolio_service.build_portfolio_detail(submission_id, student_id, db)


def _task_to_response(t) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "prompt": t.prompt,
        "instructions": t.instructions,
        "word_limit": t.word_limit,
        "recommended_time_minutes": t.recommended_time_minutes,
        "subject_id": t.subject_id,
        "exam_type_id": t.exam_type_id,
        "status": t.status.value,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
