from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.exam import (
    AnswerSaveRequest,
    AttemptAnswerResponse,
    AttemptListResponse,
    AttemptResultResponse,
    AttemptStartResponse,
    AttemptSubmitResponse,
    ExamInstanceAvailableResponse,
    IntegrityEventRequest,
)
from app.services import exam_service

router = APIRouter(tags=["exams"])


# ── Available Exams ──────────────────────────────────────────────────────────

@router.get("/exams/available", response_model=list[ExamInstanceAvailableResponse])
async def list_available_exams(
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    instances = await exam_service.list_available_exams(db=db)
    return [
        {
            "id": inst.id,
            "title": inst.title,
            "duration_minutes": inst.duration_minutes,
            "question_count": len(inst.instance_questions),
            "total_marks": sum(q.marks for q in inst.instance_questions),
        }
        for inst in instances
    ]


# ── Attempt Lifecycle ────────────────────────────────────────────────────────

@router.post(
    "/exams/{instance_id}/attempts/start",
    response_model=AttemptStartResponse,
    status_code=201,
)
async def start_attempt(
    instance_id: str,
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
    assignment_id: str | None = None,
):
    profile = await exam_service.get_student_profile_for_user(student_user.id, db)
    attempt = await exam_service.start_attempt(
        student_id=profile.id,
        instance_id=instance_id,
        db=db,
        actor_user_id=student_user.id,
        assigned_exam_id=assignment_id,
    )
    instance = await exam_service.get_exam_instance(instance_id, db)

    questions = []
    for eiq in sorted(instance.instance_questions, key=lambda q: q.order_index):
        qv = eiq.question_version
        questions.append({
            "exam_instance_question_id": eiq.id,
            "question_id": eiq.question_id,
            "question_version_id": eiq.question_version_id,
            "stem": qv.stem if qv else "",
            "correct_answer": qv.correct_answer if qv else None,
            "full_explanation": qv.full_explanation if qv else "",
            "marks": eiq.marks,
            "options_json": qv.options_json if qv else None,
            "order_index": eiq.order_index,
        })

    return {
        "attempt_id": attempt.id,
        "exam_instance_id": instance.id,
        "title": instance.title,
        "duration_minutes": instance.duration_minutes,
        "started_at": attempt.started_at,
        "expires_at": attempt.expires_at,
        "total_questions": attempt.total_questions,
        "questions": questions,
    }


@router.get("/attempts/{attempt_id}", response_model=AttemptStartResponse)
async def get_attempt(
    attempt_id: str,
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await exam_service.get_student_profile_for_user(student_user.id, db)
    attempt = await exam_service.get_attempt_for_student(
        attempt_id=attempt_id, student_id=profile.id, db=db
    )

    instance = attempt.exam_instance
    questions = []
    for eiq in sorted(instance.instance_questions, key=lambda q: q.order_index):
        qv = eiq.question_version
        answer = next(
            (a for a in attempt.answers if a.exam_instance_question_id == eiq.id),
            None,
        )
        questions.append({
            "exam_instance_question_id": eiq.id,
            "question_id": eiq.question_id,
            "question_version_id": eiq.question_version_id,
            "stem": qv.stem if qv else "",
            "correct_answer": None,  # Don't reveal correct answer before submit
            "full_explanation": "",  # Don't reveal explanation before submit
            "marks": eiq.marks,
            "options_json": qv.options_json if qv else None,
            "order_index": eiq.order_index,
        })

    return {
        "attempt_id": attempt.id,
        "exam_instance_id": instance.id,
        "title": instance.title,
        "duration_minutes": instance.duration_minutes,
        "started_at": attempt.started_at,
        "expires_at": attempt.expires_at,
        "total_questions": attempt.total_questions,
        "questions": questions,
    }


@router.patch("/attempts/{attempt_id}/answers", response_model=AttemptAnswerResponse)
async def save_answer(
    attempt_id: str,
    body: AnswerSaveRequest,
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await exam_service.get_student_profile_for_user(student_user.id, db)
    return await exam_service.save_answer(
        attempt_id=attempt_id,
        student_id=profile.id,
        exam_instance_question_id=body.exam_instance_question_id,
        selected_option=body.selected_option,
        db=db,
        actor_user_id=student_user.id,
        time_spent_seconds=body.time_spent_seconds,
    )


@router.post("/attempts/{attempt_id}/integrity-event", status_code=204)
async def record_integrity_event(
    attempt_id: str,
    body: IntegrityEventRequest,
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await exam_service.get_student_profile_for_user(student_user.id, db)
    await exam_service.record_integrity_event(
        attempt_id=attempt_id,
        student_id=profile.id,
        event_type=body.event_type,
        db=db,
    )


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptSubmitResponse)
async def submit_attempt(
    attempt_id: str,
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await exam_service.get_student_profile_for_user(student_user.id, db)
    attempt = await exam_service.submit_attempt(
        attempt_id=attempt_id, student_id=profile.id, db=db, actor_user_id=student_user.id
    )
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "score_raw": attempt.score_raw,
        "score_percent": attempt.score_percent,
        "total_questions": attempt.total_questions,
        "correct_count": attempt.correct_count,
        "submitted_at": attempt.submitted_at,
    }


@router.get("/attempts/{attempt_id}/result", response_model=AttemptResultResponse)
async def get_attempt_result(
    attempt_id: str,
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await exam_service.get_student_profile_for_user(student_user.id, db)
    return await exam_service.get_attempt_result(
        attempt_id=attempt_id, student_id=profile.id, db=db
    )


@router.get("/students/me/attempts", response_model=list[AttemptListResponse])
async def list_my_attempts(
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await exam_service.get_student_profile_for_user(student_user.id, db)
    attempts = await exam_service.list_student_attempts(student_id=profile.id, db=db)
    return [
        {
            "id": a.id,
            "exam_instance_id": a.exam_instance_id,
            "exam_title": a.exam_instance.title,
            "status": a.status,
            "started_at": a.started_at,
            "submitted_at": a.submitted_at,
            "score_percent": a.score_percent,
            "total_questions": a.total_questions,
            "correct_count": a.correct_count,
        }
        for a in attempts
    ]
