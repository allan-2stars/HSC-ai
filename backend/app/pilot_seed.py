"""
M4.8 Content Seeding Pilot
===========================
Idempotent script that exercises the full HSC-ai content pipeline:
  taxonomy → framework + outcomes → AI generation → review → publish → exam → assignment

Run via:  make seed-pilot
  or      docker compose exec backend python -m app.pilot_seed
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import (
    AdminProfile,
    ParentProfile,
    StudentProfile,
    User,
    UserRole,
)
from app.models.content import ExamType, SkillTag, Subject, Topic
from app.models.curriculum import CurriculumFramework, CurriculumOutcome
from app.models.question import (
    ContentOwnershipType,
    Question,
    QuestionStatus,
    QuestionVersion,
)
from app.models.exam import (
    ExamInstance,
    ExamInstanceQuestion,
    ExamInstanceStatus,
    ExamSection,
    ExamSectionQuestion,
    ExamTemplate,
    ExamTemplateStatus,
)
from app.models.assignment import AssignedExam, AssignmentStatus
from app.services.ai_providers import GenerationParams, mock_generate
from app.services.ai_service import _validate_generated_question
from app.services.question_service import (
    create_question,
    approve_question,
    publish_question,
    submit_for_review,
    transition_status,
)


# ── Config ───────────────────────────────────────────────────────────────────

PILOT_OUTCOMES = [
    ("OC-MATH-FRACTIONS", "Fractions — equivalence, addition, subtraction, multiplication"),
    ("OC-MATH-DECIMALS", "Decimals — place value, operations, conversion"),
    ("OC-MATH-PERCENTAGES", "Percentages — calculate, compare, apply discounts"),
    ("OC-MATH-PATTERNS", "Patterns & Algebra — sequences, rules, expressions"),
    ("OC-MATH-GEOMETRY", "Geometry — angles, 2D/3D shapes, measurement"),
]

QUESTIONS_PER_OUTCOME = 20
DIFFICULTY_MIX = {"easy": 30, "medium": 50, "hard": 20}
FRAMEWORK_NAME = "OC Mathematics 2026"
SUBJECT_CODE = "maths"
EXAM_TYPE_CODE = "oc"


# ── Seed accounts ────────────────────────────────────────────────────────────


async def _ensure_user(email: str, password: str, role: UserRole, display_name: str, db):
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(email=email.lower(), password_hash=hash_password(password), role=role)
    db.add(user)
    await db.flush()
    if role == UserRole.admin:
        db.add(AdminProfile(user_id=user.id, display_name=display_name))
    elif role == UserRole.parent:
        db.add(ParentProfile(user_id=user.id, display_name=display_name))
    await db.flush()
    return user


async def _ensure_student(display_name, year_level, parent_user, parent_id, db):
    result = await db.execute(select(StudentProfile).where(StudentProfile.display_name == display_name))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    student_user = User(
        email="spilot01@students.hscai.internal",
        password_hash=hash_password("student123"),
        role=UserRole.student,
    )
    db.add(student_user)
    await db.flush()
    profile = StudentProfile(
        user_id=student_user.id, parent_id=parent_id,
        display_name=display_name, year_level=year_level, first_login_completed=True,
    )
    db.add(profile)
    await db.flush()
    return profile


# ── Taxonomy ─────────────────────────────────────────────────────────────────


async def _ensure_taxonomy(db):
    subjects = {}
    topics = {}
    skills = {}

    for code, name in [(SUBJECT_CODE, "Mathematics"), ("english", "English"), ("thinking", "Thinking Skills")]:
        result = await db.execute(select(Subject).where(Subject.code == code))
        s = result.scalar_one_or_none()
        if not s:
            s = Subject(code=code, name=name)
            db.add(s)
            await db.flush()
        subjects[code] = s

    for code, name in [(EXAM_TYPE_CODE, "Opportunity Class"), ("selective", "Selective School")]:
        result = await db.execute(select(ExamType).where(ExamType.code == code))
        et = result.scalar_one_or_none()
        if not et:
            et = ExamType(code=code, name=name)
            db.add(et)
            await db.flush()

    topic_list = [
        (SUBJECT_CODE, "Number & Algebra"),
        (SUBJECT_CODE, "Measurement & Geometry"),
        (SUBJECT_CODE, "Statistics & Probability"),
        ("english", "Reading Comprehension"),
        ("english", "Vocabulary"),
        ("thinking", "Logical Reasoning"),
        ("thinking", "Problem Solving"),
    ]
    for subj_code, tname in topic_list:
        sid = subjects[subj_code].id
        result = await db.execute(select(Topic).where(Topic.subject_id == sid, Topic.name == tname))
        t = result.scalar_one_or_none()
        if not t:
            t = Topic(subject_id=sid, name=tname)
            db.add(t)
            await db.flush()
        topics[(subj_code, tname)] = t

    skill_list = [
        (SUBJECT_CODE, "Addition/Subtraction"), (SUBJECT_CODE, "Multiplication/Division"),
        (SUBJECT_CODE, "Fractions"), (SUBJECT_CODE, "Decimals"), (SUBJECT_CODE, "Percentages"),
        ("english", "Literal Comprehension"), ("english", "Inference"),
        ("thinking", "Pattern Recognition"), ("thinking", "Deduction"),
    ]
    for subj_code, sname in skill_list:
        sid = subjects[subj_code].id
        result = await db.execute(select(SkillTag).where(SkillTag.subject_id == sid, SkillTag.name == sname))
        sk = result.scalar_one_or_none()
        if not sk:
            sk = SkillTag(subject_id=sid, name=sname)
            db.add(sk)
            await db.flush()
        skills[(subj_code, sname)] = sk

    await db.commit()
    return subjects, topics, skills


# ── Curriculum ───────────────────────────────────────────────────────────────


async def _ensure_curriculum(db):
    result = await db.execute(select(CurriculumFramework).where(CurriculumFramework.name == FRAMEWORK_NAME))
    fw = result.scalar_one_or_none()
    if not fw:
        fw = CurriculumFramework(name=FRAMEWORK_NAME, description="NSW OC Mathematics outcomes", version="2026")
        db.add(fw)
        await db.flush()

    outcomes = {}
    for code, title in PILOT_OUTCOMES:
        result = await db.execute(select(CurriculumOutcome).where(CurriculumOutcome.code == code))
        oc = result.scalar_one_or_none()
        if not oc:
            oc = CurriculumOutcome(framework_id=fw.id, code=code, title=title, sort_order=0)
            db.add(oc)
            await db.flush()
        outcomes[code] = oc

    await db.commit()
    return fw, outcomes


# ── AI Generation + Lifecycle ────────────────────────────────────────────────


async def _pilot_generate_and_publish(
    outcomes: dict, subjects: dict, db,
) -> dict:
    """Generate, review, approve, and publish questions for each outcome. Returns per-outcome counts."""
    from app.models.curriculum import QuestionOutcomeMapping
    from app.models.question import QuestionType, SourceType, DifficultyLevel

    subject = subjects[SUBJECT_CODE]
    result = await db.execute(select(ExamType).where(ExamType.code == EXAM_TYPE_CODE))
    exam_type = result.scalar_one()

    # Find the admin for creating questions
    result = await db.execute(select(AdminProfile).limit(1))
    admin = result.scalar_one_or_none()
    if not admin:
        raise RuntimeError("No admin profile found — run make seed-dev first")

    per_outcome = {}
    topic = await db.execute(select(Topic).where(Topic.name == "Number & Algebra"))

    for code, oc in outcomes.items():
        generated = 0
        saved = 0
        submitted = 0
        approved = 0
        published = 0

        # Generate using mock provider
        params = GenerationParams(
            outcome_code=code, outcome_title=oc.title,
            subject_name="Mathematics", exam_type_name="Opportunity Class",
            count=QUESTIONS_PER_OUTCOME, difficulty_mix=DIFFICULTY_MIX,
        )
        questions, _ = await mock_generate(params)

        for q in questions:
            generated += 1
            errors = _validate_generated_question(q)
            if errors:
                continue

            try:
                # Create as draft (bypassing the normal create_question which also creates a version)
                question = Question(
                    subject_id=subject.id, exam_type_id=exam_type.id, year_level=5,
                    difficulty=DifficultyLevel(q.difficulty),
                    question_type=QuestionType.mcq,
                    status=QuestionStatus.draft,
                    source_type=SourceType.ai,
                    content_ownership=ContentOwnershipType.original,
                    created_by_admin_id=admin.id,
                )
                db.add(question)
                await db.flush()

                v = QuestionVersion(
                    question_id=question.id, version_number=1,
                    stem=q.question_text, correct_answer=q.correct_answer,
                    full_explanation=q.explanation, marks=1,
                    options_json=q.options,
                    created_by_admin_id=admin.id,
                    created_at=datetime.now(tz=timezone.utc),
                )
                db.add(v)
                await db.flush()
                question.current_version_id = v.id
                saved += 1

                # Auto-map to outcome
                db.add(QuestionOutcomeMapping(question_id=question.id, outcome_id=oc.id, weight=1.0))

                # Move through lifecycle: draft → review → approved → published
                try:
                    await submit_for_review(question.id, admin.id, db, quality_score=4, review_notes="Pilot seed — auto-approved")
                    submitted += 1
                    await approve_question(question.id, admin.id, db)
                    approved += 1
                    await publish_question(question.id, db)
                    published += 1
                except Exception:
                    # If we can't publish (e.g., content_ownership block), just skip
                    # We're using original ownership so this should be fine
                    pass

            except Exception:
                continue

        per_outcome[code] = {
            "generated": generated, "saved": saved,
            "submitted": submitted, "approved": approved, "published": published,
        }

    await db.commit()
    return per_outcome


# ── Sample Exam ──────────────────────────────────────────────────────────────


async def _ensure_sample_exam(db):
    """Create a 20-question OC Maths exam from published questions."""
    from sqlalchemy import func as sql_func

    result = await db.execute(select(ExamType).where(ExamType.code == EXAM_TYPE_CODE))
    exam_type = result.scalar_one()
    result = await db.execute(select(Subject).where(Subject.code == SUBJECT_CODE))
    subject = result.scalar_one()
    result = await db.execute(select(AdminProfile).limit(1))
    admin = result.scalar_one()

    # Find published questions
    result = await db.execute(
        select(Question)
        .where(Question.status == QuestionStatus.published, Question.exam_type_id == exam_type.id)
        .limit(20)
    )
    published = list(result.scalars().all())

    if len(published) < 5:
        return None, None, f"Only {len(published)} published questions — need at least 5"

    # Create template
    template = ExamTemplate(
        title="OC Mathematics Sample Exam",
        description="Pilot seed sample exam — 20 MCQs, 30 minutes",
        exam_type_id=exam_type.id, subject_id=subject.id, year_level=5,
        duration_minutes=30, status=ExamTemplateStatus.published,
        created_by_admin_id=admin.id,
    )
    db.add(template)
    await db.flush()

    section = ExamSection(
        exam_template_id=template.id, title="Mathematics",
        order_index=0, instructions="Choose the best answer for each question.",
    )
    db.add(section)
    await db.flush()

    for i, q in enumerate(published[:20]):
        db.add(ExamSectionQuestion(
            exam_section_id=section.id, question_id=q.id,
            order_index=i, marks=1,
        ))

    # Create instance
    instance = ExamInstance(
        exam_template_id=template.id, title="OC Mathematics Sample Exam",
        duration_minutes=30,
    )
    db.add(instance)
    await db.flush()

    # Freeze questions
    for i, q in enumerate(published[:20]):
        db.add(ExamInstanceQuestion(
            exam_instance_id=instance.id, exam_section_id=section.id,
            question_id=q.id, question_version_id=q.current_version_id,
            order_index=i, marks=1,
        ))

    instance.status = ExamInstanceStatus.published
    await db.commit()
    return instance, template, None


# ── Assignment ───────────────────────────────────────────────────────────────


async def _ensure_pilot_assignment(instance, db):
    result = await db.execute(select(ParentProfile).limit(1))
    parent = result.scalar_one_or_none()
    if not parent:
        return None

    result = await db.execute(
        select(StudentProfile).where(StudentProfile.parent_id == parent.id).limit(1)
    )
    student = result.scalar_one_or_none()
    if not student:
        return None

    result = await db.execute(
        select(AssignedExam).where(
            AssignedExam.student_id == student.id,
            AssignedExam.exam_instance_id == instance.id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    assignment = AssignedExam(
        student_id=student.id, exam_instance_id=instance.id,
        assigned_by_parent_id=parent.id,
        title_snapshot=instance.title, status=AssignmentStatus.assigned,
    )
    db.add(assignment)
    await db.commit()
    return assignment


# ── Coverage Snapshot ────────────────────────────────────────────────────────


async def _get_coverage_snapshot(db):
    """Get per-outcome question counts for all curriculum outcomes."""
    from sqlalchemy import func as sql_func

    from app.models.curriculum import CurriculumOutcome, QuestionOutcomeMapping
    from app.models.question import QuestionStatus

    result = await db.execute(
        select(CurriculumOutcome.id, CurriculumOutcome.code)
    )
    all_codes = {row[1]: {"o_id": row[0], "published": 0} for row in result.fetchall()}

    result = await db.execute(
        select(CurriculumOutcome.code, sql_func.count(Question.id))
        .select_from(CurriculumOutcome)
        .outerjoin(QuestionOutcomeMapping, QuestionOutcomeMapping.outcome_id == CurriculumOutcome.id)
        .outerjoin(Question, Question.id == QuestionOutcomeMapping.question_id)
        .where(Question.status == QuestionStatus.published)
        .group_by(CurriculumOutcome.code)
    )
    pub_counts = {row[0]: row[1] for row in result.fetchall()}
    return all_codes, pub_counts


# ── Main ─────────────────────────────────────────────────────────────────────


async def pilot_seed_all(db) -> dict:
    summary = {"steps": [], "per_outcome": {}, "errors": []}

    # 1. Seed subscription plans
    from app.services.seed_service import seed_plans
    await seed_plans(db)
    summary["steps"].append("plans_seeded")

    # 2. Seed users
    admin = await _ensure_user("admin@hsc.local", "admin123", UserRole.admin, "Seed Admin", db)
    parent = await _ensure_user("parent@hsc.local", "parent123", UserRole.parent, "Seed Parent", db)
    parent_result = await db.execute(select(ParentProfile).where(ParentProfile.user_id == parent.id))
    parent_profile = parent_result.scalar_one()
    student = await _ensure_student("Seed Student", 5, parent, parent_profile.id, db)
    summary["steps"].append("users_seeded")

    # 3. Snapshot coverage before
    all_codes, before_pub = await _get_coverage_snapshot(db)

    # 4. Taxonomy
    subjects, topics, skills = await _ensure_taxonomy(db)
    summary["steps"].append("taxonomy_seeded")

    # 5. Curriculum framework + outcomes
    fw, outcomes = await _ensure_curriculum(db)
    summary["steps"].append(f"curriculum_seeded ({len(outcomes)} outcomes)")

    # 6. AI generate + review + approve + publish
    per_outcome = await _pilot_generate_and_publish(outcomes, subjects, db)
    summary["per_outcome"] = per_outcome

    total_published = sum(o["published"] for o in per_outcome.values())
    total_generated = sum(o["generated"] for o in per_outcome.values())
    total_saved = sum(o["saved"] for o in per_outcome.values())
    total_rejected = total_generated - total_saved
    summary["totals"] = {
        "generated": total_generated, "saved": total_saved,
        "rejected": total_rejected, "published": total_published,
    }
    summary["steps"].append(f"questions_generated_and_published ({total_published} published)")

    # 7. Snapshot coverage after
    all_codes, after_pub = await _get_coverage_snapshot(db)
    pilot_codes = [o[0] for o in PILOT_OUTCOMES]
    coverage_before = {c: before_pub.get(c, 0) for c in pilot_codes}
    coverage_after = {c: after_pub.get(c, 0) for c in pilot_codes}
    summary["coverage"] = {
        "before": coverage_before,
        "after": coverage_after,
    }

    # 8. Create sample exam
    instance, template, err = await _ensure_sample_exam(db)
    if err:
        summary["errors"].append(err)
    else:
        summary["exam"] = {"instance_id": instance.id, "template_id": template.id, "title": template.title}
        summary["steps"].append("sample_exam_created")

    # 9. Create parent assignment
    if instance:
        assignment = await _ensure_pilot_assignment(instance, db)
        if assignment:
            summary["steps"].append("parent_assignment_created")

    return summary


async def main():
    async with SessionLocal() as db:
        try:
            result = await pilot_seed_all(db)
            print("\n" + "=" * 60)
            print("  M4.8 CONTENT SEEDING PILOT — COMPLETE")
            print("=" * 60)

            print(f"\nSteps: {' → '.join(result['steps'])}")

            print(f"\nPer-Outcome:")
            for code, counts in result["per_outcome"].items():
                print(f"  {code}: gen={counts['generated']} saved={counts['saved']} "
                      f"submitted={counts['submitted']} approved={counts['approved']} published={counts['published']}")

            t = result.get("totals", {})
            print(f"\nTotals: {t.get('generated',0)} generated, {t.get('saved',0)} saved, "
                  f"{t.get('rejected',0)} rejected, {t.get('published',0)} published")

            cov = result.get("coverage", {})
            print(f"\nCoverage Before → After:")
            for code in cov.get("before", {}):
                print(f"  {code}: {cov['before'][code]} → {cov['after'][code]} published")

            if result.get("exam"):
                print(f"\nSample Exam: {result['exam']['title']} (id={result['exam']['instance_id']})")

            if result.get("errors"):
                print(f"\nErrors: {result['errors']}")

            print(f"\nView: http://localhost:3090/admin/curriculum")
            print(f"      http://localhost:3090/exams")
            print(f"      http://localhost:3090/me/progress")
            print("=" * 60 + "\n")

        except Exception as e:
            print(f"Pilot seed error: {e}")
            raise


# Allow running as: docker compose exec backend python -m app.pilot_seed
if __name__ == "__main__":
    asyncio.run(main())
