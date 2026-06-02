from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.exam import (
    Attempt,
    AttemptAnswer,
    AttemptIntegrityEvent,
    AttemptStatus,
    ExamInstance,
    ExamInstanceQuestion,
    ExamInstanceStatus,
    ExamSection,
    ExamSectionQuestion,
    ExamTemplate,
    ExamTemplateStatus,
)
from app.models.question import Question, QuestionStatus, QuestionVersion
from app.models.user import StudentProfile
from app.services import audit_service

# ── Status transition maps ─────────────────────────────────────────────────

_TEMPLATE_TRANSITIONS: dict[ExamTemplateStatus, frozenset[ExamTemplateStatus]] = {
    ExamTemplateStatus.draft: frozenset({ExamTemplateStatus.review}),
    ExamTemplateStatus.review: frozenset({ExamTemplateStatus.approved, ExamTemplateStatus.draft}),
    ExamTemplateStatus.approved: frozenset({ExamTemplateStatus.published, ExamTemplateStatus.draft}),
    ExamTemplateStatus.published: frozenset({ExamTemplateStatus.archived}),
    ExamTemplateStatus.archived: frozenset(),
}

_INSTANCE_TRANSITIONS: dict[ExamInstanceStatus, frozenset[ExamInstanceStatus]] = {
    ExamInstanceStatus.draft: frozenset({ExamInstanceStatus.published, ExamInstanceStatus.archived}),
    ExamInstanceStatus.published: frozenset({ExamInstanceStatus.archived}),
    ExamInstanceStatus.archived: frozenset(),
}


# ── ExamTemplate CRUD ──────────────────────────────────────────────────────

async def create_exam_template(
    title: str,
    exam_type_id: str,
    duration_minutes: int,
    created_by_admin_id: str,
    db: AsyncSession,
    description: str | None = None,
    subject_id: str | None = None,
    year_level: int | None = None,
) -> ExamTemplate:
    template = ExamTemplate(
        title=title.strip(),
        description=description,
        exam_type_id=exam_type_id,
        subject_id=subject_id,
        year_level=year_level,
        duration_minutes=duration_minutes,
        status=ExamTemplateStatus.draft,
        created_by_admin_id=created_by_admin_id,
    )
    db.add(template)
    await db.commit()
    # Re-fetch with eager loading so Pydantic can serialize sections
    return await get_exam_template(template.id, db)


async def get_exam_template(template_id: str, db: AsyncSession) -> ExamTemplate:
    result = await db.execute(
        select(ExamTemplate)
        .options(
            selectinload(ExamTemplate.sections)
            .selectinload(ExamSection.section_questions)
        )
        .where(ExamTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam template not found")
    return template


async def list_exam_templates(
    db: AsyncSession,
    status_filter: ExamTemplateStatus | None = None,
) -> list[ExamTemplate]:
    query = select(ExamTemplate)
    if status_filter is not None:
        query = query.where(ExamTemplate.status == status_filter)
    result = await db.execute(query.order_by(ExamTemplate.created_at.desc()))
    return list(result.scalars().all())


async def update_template_status(
    template_id: str,
    new_status: ExamTemplateStatus,
    db: AsyncSession,
) -> ExamTemplate:
    template = await get_exam_template(template_id, db)

    allowed = _TEMPLATE_TRANSITIONS.get(template.status, frozenset())
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{template.status.value}' to '{new_status.value}'",
        )

    if new_status == ExamTemplateStatus.published:
        if not template.sections:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot publish: template has no sections",
            )
        for section in template.sections:
            if not section.section_questions:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot publish: section '{section.title}' has no questions",
                )
            for sq in section.section_questions:
                question = await db.get(Question, sq.question_id)
                if not question:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Cannot publish: question {sq.question_id} not found",
                    )
                if question.status != QuestionStatus.published:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Cannot publish: question {sq.question_id} is not published "
                            f"(status: {question.status.value})"
                        ),
                    )
                if not question.current_version_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Cannot publish: question {sq.question_id} has no current version",
                    )

    template.status = new_status
    await db.commit()
    return await get_exam_template(template_id, db)


# ── ExamSection CRUD ──────────────────────────────────────────────────────

async def create_exam_section(
    template_id: str,
    title: str,
    db: AsyncSession,
    order_index: int = 0,
    duration_minutes: int | None = None,
    instructions: str | None = None,
) -> ExamSection:
    template = await get_exam_template(template_id, db)
    if template.status == ExamTemplateStatus.archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add section to archived template",
        )

    section = ExamSection(
        exam_template_id=template_id,
        title=title.strip(),
        order_index=order_index,
        duration_minutes=duration_minutes,
        instructions=instructions,
    )
    db.add(section)
    await db.commit()

    # Re-fetch with eager loading for Pydantic serialization
    result = await db.execute(
        select(ExamSection)
        .options(selectinload(ExamSection.section_questions))
        .where(ExamSection.id == section.id)
    )
    return result.scalar_one()


async def add_question_to_section(
    section_id: str,
    question_id: str,
    db: AsyncSession,
    order_index: int = 0,
    marks: int = 1,
) -> ExamSectionQuestion:
    result = await db.execute(
        select(ExamSection).where(ExamSection.id == section_id)
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    sq = ExamSectionQuestion(
        exam_section_id=section_id,
        question_id=question_id,
        order_index=order_index,
        marks=marks,
    )
    db.add(sq)
    await db.commit()
    await db.refresh(sq)
    return sq


# ── ExamInstance CRUD ─────────────────────────────────────────────────────

async def create_exam_instance(
    template_id: str,
    db: AsyncSession,
    title: str | None = None,
) -> ExamInstance:
    template = await get_exam_template(template_id, db)
    if template.status != ExamTemplateStatus.published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Template must be published before creating an instance",
        )

    instance = ExamInstance(
        exam_template_id=template_id,
        title=title or template.title,
        duration_minutes=template.duration_minutes,
        status=ExamInstanceStatus.draft,
        published_at=None,
    )
    db.add(instance)
    await db.flush()

    global_index = 0
    for section in sorted(template.sections, key=lambda s: s.order_index):
        for sq in sorted(section.section_questions, key=lambda sq: sq.order_index):
            question = await db.get(Question, sq.question_id)
            if not question or not question.current_version_id:
                continue

            eiq = ExamInstanceQuestion(
                exam_instance_id=instance.id,
                exam_section_id=section.id,
                question_id=sq.question_id,
                question_version_id=question.current_version_id,
                order_index=global_index,
                marks=sq.marks,
            )
            db.add(eiq)
            global_index += 1

    await db.commit()
    return await get_exam_instance(instance.id, db)


async def get_exam_instance(instance_id: str, db: AsyncSession) -> ExamInstance:
    result = await db.execute(
        select(ExamInstance)
        .options(
            selectinload(ExamInstance.instance_questions)
            .selectinload(ExamInstanceQuestion.question_version)
        )
        .where(ExamInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam instance not found")
    return instance


async def publish_exam_instance(
    instance_id: str,
    db: AsyncSession,
    admin_user_id: str,
) -> ExamInstance:
    instance = await get_exam_instance(instance_id, db)

    if instance.status != ExamInstanceStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot publish instance with status '{instance.status.value}'",
        )

    if not instance.instance_questions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot publish: instance has no questions",
        )

    instance.status = ExamInstanceStatus.published
    instance.published_at = datetime.now(tz=timezone.utc)
    await db.commit()

    await audit_service.log_action(
        db=db,
        action="exam_instance_published",
        actor_user_id=admin_user_id,
        actor_role="admin",
        target_type="exam_instance",
        target_id=instance_id,
        metadata={"question_count": len(instance.instance_questions)},
    )
    await db.commit()

    return await get_exam_instance(instance_id, db)


async def list_exam_instances(
    db: AsyncSession,
    status_filter: ExamInstanceStatus | None = None,
) -> list[ExamInstance]:
    query = select(ExamInstance)
    if status_filter is not None:
        query = query.where(ExamInstance.status == status_filter)
    result = await db.execute(query.order_by(ExamInstance.created_at.desc()))
    return list(result.scalars().all())


# ── Student: Available Exams ──────────────────────────────────────────────

async def list_available_exams(db: AsyncSession) -> list[ExamInstance]:
    result = await db.execute(
        select(ExamInstance)
        .options(selectinload(ExamInstance.instance_questions))
        .where(ExamInstance.status == ExamInstanceStatus.published)
        .order_by(ExamInstance.published_at.desc())
    )
    return list(result.scalars().all())


# ── Attempt Lifecycle ─────────────────────────────────────────────────────

async def start_attempt(
    student_id: str,
    instance_id: str,
    db: AsyncSession,
    actor_user_id: str = "",
    assigned_exam_id: str | None = None,
) -> Attempt:
    instance = await get_exam_instance(instance_id, db)

    if instance.status != ExamInstanceStatus.published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot start attempt on unpublished exam instance",
        )

    now = datetime.now(tz=timezone.utc)
    attempt = Attempt(
        student_id=student_id,
        exam_instance_id=instance_id,
        status=AttemptStatus.in_progress,
        started_at=now,
        expires_at=now + timedelta(minutes=instance.duration_minutes),
        total_questions=len(instance.instance_questions),
        assigned_exam_id=assigned_exam_id,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    # If started from an assignment, transition it to started
    if assigned_exam_id:
        from app.services import assignment_service
        await assignment_service.transition_on_attempt_start(assigned_exam_id, attempt.id, db)

    await audit_service.log_action(
        db=db,
        action="attempt_started",
        actor_user_id=actor_user_id,
        actor_role="student",
        target_type="attempt",
        target_id=attempt.id,
        metadata={"instance_id": instance_id},
    )
    await db.commit()

    return attempt


async def get_attempt_for_student(
    attempt_id: str,
    student_id: str,
    db: AsyncSession,
) -> Attempt:
    result = await db.execute(
        select(Attempt)
        .options(
            selectinload(Attempt.answers),
            selectinload(Attempt.exam_instance)
            .selectinload(ExamInstance.instance_questions)
            .selectinload(ExamInstanceQuestion.question_version),
        )
        .where(Attempt.id == attempt_id)
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.student_id != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return attempt


async def save_answer(
    attempt_id: str,
    student_id: str,
    exam_instance_question_id: str,
    selected_option: str | None,
    db: AsyncSession,
    actor_user_id: str = "",
    time_spent_seconds: int = 0,
) -> AttemptAnswer:
    attempt = await get_attempt_for_student(attempt_id, student_id, db)

    if attempt.status != AttemptStatus.in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify answers: attempt is not in progress",
        )

    # Verify the question belongs to this attempt's instance
    valid_question_ids = {q.id for q in attempt.exam_instance.instance_questions}
    if exam_instance_question_id not in valid_question_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question does not belong to this exam instance",
        )

    now = datetime.now(tz=timezone.utc)

    # Upsert: find existing answer or create new
    result = await db.execute(
        select(AttemptAnswer).where(
            AttemptAnswer.attempt_id == attempt_id,
            AttemptAnswer.exam_instance_question_id == exam_instance_question_id,
        )
    )
    answer = result.scalar_one_or_none()

    if answer:
        answer.selected_option = selected_option
        answer.time_spent_seconds += time_spent_seconds
        answer.answered_at = now
    else:
        answer = AttemptAnswer(
            attempt_id=attempt_id,
            exam_instance_question_id=exam_instance_question_id,
            selected_option=selected_option,
            time_spent_seconds=time_spent_seconds,
            answered_at=now,
        )
        db.add(answer)

    await db.commit()
    await db.refresh(answer)

    await audit_service.log_action(
        db=db,
        action="answer_saved",
        actor_user_id=actor_user_id,
        actor_role="student",
        target_type="attempt_answer",
        target_id=answer.id,
        metadata={"attempt_id": attempt_id},
    )
    await db.commit()

    return answer


# ── Integrity Events ─────────────────────────────────────────────────────────

async def record_integrity_event(
    attempt_id: str,
    student_id: str,
    event_type: str,
    db: AsyncSession,
) -> AttemptIntegrityEvent:
    attempt = await get_attempt_for_student(attempt_id, student_id, db)

    if attempt.status != AttemptStatus.in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot record integrity event: attempt is not in progress",
        )

    event = AttemptIntegrityEvent(
        attempt_id=attempt_id,
        event_type=event_type,
        metadata_json=None,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


# ── Submit ───────────────────────────────────────────────────────────────────

async def submit_attempt(
    attempt_id: str,
    student_id: str,
    db: AsyncSession,
    actor_user_id: str = "",
) -> Attempt:
    attempt = await get_attempt_for_student(attempt_id, student_id, db)

    if attempt.status != AttemptStatus.in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attempt has already been submitted",
        )

    now = datetime.now(tz=timezone.utc)
    is_expired = now > attempt.expires_at

    instance_questions = attempt.exam_instance.instance_questions
    question_map = {q.id: q for q in instance_questions}

    correct_count = 0
    total_marks = sum(q.marks for q in instance_questions)
    score_raw = 0

    for answer in attempt.answers:
        eiq = question_map.get(answer.exam_instance_question_id)
        if not eiq or not eiq.question_version:
            answer.is_correct = False
            continue

        correct_answer = eiq.question_version.correct_answer
        if correct_answer and answer.selected_option == correct_answer:
            answer.is_correct = True
            correct_count += 1
            score_raw += eiq.marks
        else:
            answer.is_correct = False

    attempt.status = AttemptStatus.expired if is_expired else AttemptStatus.submitted
    attempt.submitted_at = now
    attempt.correct_count = correct_count
    attempt.score_raw = score_raw
    attempt.score_percent = round((score_raw / total_marks) * 100, 1) if total_marks > 0 else 0.0

    # Build integrity summary
    result = await db.execute(
        select(AttemptIntegrityEvent).where(AttemptIntegrityEvent.attempt_id == attempt_id)
    )
    integrity_events = list(result.scalars().all())
    attempt.integrity_summary_json = {
        "fullscreen_exit_count": sum(1 for e in integrity_events if e.event_type == "fullscreen_exit"),
        "tab_hidden_count": sum(1 for e in integrity_events if e.event_type == "tab_hidden"),
        "copy_attempt_count": sum(1 for e in integrity_events if e.event_type == "copy_attempt"),
        "paste_attempt_count": sum(1 for e in integrity_events if e.event_type == "paste_attempt"),
    }

    await db.commit()
    await db.refresh(attempt)

    # If this attempt was linked to a parent assignment, mark it completed
    if attempt.assigned_exam_id:
        from app.services import assignment_service
        await assignment_service.transition_on_attempt_submit(attempt.assigned_exam_id, db)

    action = "attempt_expired" if is_expired else "attempt_submitted"
    await audit_service.log_action(
        db=db,
        action=action,
        actor_user_id=actor_user_id,
        actor_role="student",
        target_type="attempt",
        target_id=attempt_id,
        metadata={
            "score_percent": attempt.score_percent,
            "correct_count": correct_count,
            "total_questions": attempt.total_questions,
        },
    )
    await db.commit()

    return attempt


async def get_attempt_result(
    attempt_id: str,
    student_id: str,
    db: AsyncSession,
) -> dict:
    attempt = await get_attempt_for_student(attempt_id, student_id, db)

    if attempt.status == AttemptStatus.in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attempt has not been submitted yet",
        )

    questions = []
    for eiq in sorted(
        attempt.exam_instance.instance_questions,
        key=lambda q: q.order_index,
    ):
        answer = next(
            (a for a in attempt.answers if a.exam_instance_question_id == eiq.id),
            None,
        )
        marks_awarded = 0
        if answer and answer.is_correct:
            marks_awarded = eiq.marks

        questions.append({
            "exam_instance_question_id": eiq.id,
            "question_id": eiq.question_id,
            "stem": eiq.question_version.stem if eiq.question_version else "",
            "correct_answer": eiq.question_version.correct_answer if eiq.question_version else None,
            "full_explanation": eiq.question_version.full_explanation if eiq.question_version else "",
            "marks": eiq.marks,
            "options_json": eiq.question_version.options_json if eiq.question_version else None,
            "order_index": eiq.order_index,
            "selected_option": answer.selected_option if answer else None,
            "is_correct": answer.is_correct if answer else None,
            "marks_awarded": marks_awarded,
        })

    return {
        "attempt_id": attempt.id,
        "exam_instance_id": attempt.exam_instance_id,
        "title": attempt.exam_instance.title,
        "status": attempt.status,
        "started_at": attempt.started_at,
        "expires_at": attempt.expires_at,
        "submitted_at": attempt.submitted_at,
        "score_raw": attempt.score_raw,
        "score_percent": attempt.score_percent,
        "total_questions": attempt.total_questions,
        "correct_count": attempt.correct_count,
        "questions": questions,
    }


async def list_student_attempts(
    student_id: str,
    db: AsyncSession,
) -> list[Attempt]:
    result = await db.execute(
        select(Attempt)
        .options(selectinload(Attempt.exam_instance))
        .where(Attempt.student_id == student_id)
        .order_by(Attempt.started_at.desc())
    )
    return list(result.scalars().all())


async def get_student_profile_for_user(
    user_id: str,
    db: AsyncSession,
) -> StudentProfile:
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )
    return profile
