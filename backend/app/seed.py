"""
Development seed command — run inside the backend container or via:
  docker compose exec backend python -m app.seed

Creates: admin, parent, student, exam types, subjects, topics, skill tags,
curriculum framework + outcomes, 10+ MCQ questions (published), question pool,
exam template, published exam instance, and a parent assignment.

Idempotent — checks for existing data before creating.
"""
import asyncio

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.models.question import (
    ContentOwnershipType,
    DifficultyLevel,
    PoolType,
    Question,
    QuestionPool,
    QuestionPoolMembership,
    QuestionStatus,
    QuestionType,
    QuestionVersion,
    question_skill_tags,
)
from app.models.curriculum import CurriculumFramework, CurriculumOutcome
from app.models.exam import (
    ExamSection,
    ExamSectionQuestion,
    ExamInstance,
    ExamInstanceQuestion,
    ExamInstanceStatus,
    ExamTemplate,
    ExamTemplateStatus,
)
from app.models.assignment import AssignedExam, AssignmentStatus
from app.services.audit_service import log_action


# ── Seed accounts ────────────────────────────────────────────────────────────

SEED_ADMIN = {"email": "admin@hsc.local", "password": "admin123", "name": "Seed Admin"}
SEED_PARENT = {"email": "parent@hsc.local", "password": "parent123", "name": "Seed Parent"}
SEED_STUDENT = {"display_name": "Seed Student", "year_level": 5, "initial_password": "student123"}


async def _ensure_user(
    email: str, password: str, role: UserRole, display_name: str, db: AsyncSession
) -> User:
    """Create user if not exists; return the user."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(email=email.lower(), password_hash=hash_password(password), role=role)
    db.add(user)
    await db.flush()

    profile = None
    if role == UserRole.admin:
        profile = AdminProfile(user_id=user.id, display_name=display_name)
    elif role == UserRole.parent:
        profile = ParentProfile(user_id=user.id, display_name=display_name)
    db.add(profile)
    await db.flush()
    return user


async def _ensure_student(
    display_name: str, year_level: int, initial_password: str,
    parent_id: str, parent_user: User, db: AsyncSession,
) -> StudentProfile:
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.display_name == display_name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    short_id = "seed01"
    login_email = f"s{short_id}@students.hscai.internal"
    student_user = User(
        email=login_email,
        password_hash=hash_password(initial_password),
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

SEED_EXAM_TYPES = [
    {"code": "oc", "name": "Opportunity Class"},
    {"code": "selective", "name": "Selective School"},
]
SEED_SUBJECTS = [
    {"code": "maths", "name": "Mathematics", "topics": [
        {"name": "Number & Algebra", "skills": ["Addition/Subtraction", "Multiplication/Division", "Fractions", "Decimals"]},
        {"name": "Measurement & Geometry", "skills": ["Area & Perimeter", "Angles", "Volume"]},
        {"name": "Statistics & Probability", "skills": ["Data Interpretation", "Chance"]},
    ]},
    {"code": "english", "name": "English", "topics": [
        {"name": "Reading Comprehension", "skills": ["Literal Comprehension", "Inference", "Main Idea"]},
        {"name": "Vocabulary", "skills": ["Word Meaning", "Synonyms/Antonyms"]},
    ]},
    {"code": "thinking", "name": "Thinking Skills", "topics": [
        {"name": "Logical Reasoning", "skills": ["Pattern Recognition", "Deduction", "Sequences"]},
        {"name": "Problem Solving", "skills": ["Word Problems", "Spatial Reasoning"]},
    ]},
]


async def _ensure_taxonomy(db: AsyncSession) -> dict:
    """Create exam types, subjects, topics, skill tags. Returns {exam_type_code: ExamType.id, ...}"""
    exam_types = {}
    for et in SEED_EXAM_TYPES:
        result = await db.execute(select(ExamType).where(ExamType.code == et["code"]))
        obj = result.scalar_one_or_none()
        if not obj:
            obj = ExamType(code=et["code"], name=et["name"])
            db.add(obj)
            await db.flush()
        exam_types[et["code"]] = obj

    subjects = {}
    for subj in SEED_SUBJECTS:
        result = await db.execute(select(Subject).where(Subject.code == subj["code"]))
        s = result.scalar_one_or_none()
        if not s:
            s = Subject(code=subj["code"], name=subj["name"])
            db.add(s)
            await db.flush()

        data = {"obj": s, "topics": []}
        for t_data in subj["topics"]:
            topic_name = t_data["name"]
            result = await db.execute(
                select(Topic).where(Topic.subject_id == s.id, Topic.name == topic_name)
            )
            t = result.scalar_one_or_none()
            if not t:
                t = Topic(subject_id=s.id, name=topic_name)
                db.add(t)
                await db.flush()

            skills = []
            for skill_name in t_data["skills"]:
                result = await db.execute(
                    select(SkillTag).where(SkillTag.subject_id == s.id, SkillTag.name == skill_name)
                )
                sk = result.scalar_one_or_none()
                if not sk:
                    sk = SkillTag(subject_id=s.id, name=skill_name)
                    db.add(sk)
                    await db.flush()
                skills.append(sk)
            data["topics"].append({"obj": t, "skills": skills})
        subjects[subj["code"]] = data

    await db.commit()
    return {"exam_types": exam_types, "subjects": subjects}


# ── Curriculum ───────────────────────────────────────────────────────────────


async def _ensure_curriculum(db: AsyncSession) -> dict:
    from app.models.curriculum import CurriculumFramework, CurriculumOutcome
    result = await db.execute(select(CurriculumFramework).where(CurriculumFramework.name == "OC Mathematics 2026"))
    fw = result.scalar_one_or_none()
    if not fw:
        fw = CurriculumFramework(name="OC Mathematics 2026", description="NSW OC Mathematics curriculum outcomes", version="2026")
        db.add(fw)
        await db.flush()

    outcomes_code_map = {}
    for o_data in [
        ("OC-MATH-NUM", "Number & Algebra — whole number operations"),
        ("OC-MATH-FRAC", "Fractions — equivalence, addition, subtraction"),
        ("OC-MATH-DEC", "Decimals — place value and operations"),
        ("OC-MATH-MEAS", "Measurement — length, area, volume, time"),
        ("OC-MATH-GEOM", "Geometry — angles, 2D and 3D shapes"),
        ("OC-MATH-DATA", "Data — tables, graphs, interpretation"),
    ]:
        result = await db.execute(select(CurriculumOutcome).where(CurriculumOutcome.code == o_data[0]))
        oc = result.scalar_one_or_none()
        if not oc:
            oc = CurriculumOutcome(framework_id=fw.id, code=o_data[0], title=o_data[1], sort_order=0)
            db.add(oc)
            await db.flush()
        outcomes_code_map[o_data[0]] = oc

    await db.commit()
    return {"framework": fw, "outcomes": outcomes_code_map}


# ── Questions ────────────────────────────────────────────────────────────────

_MCQ_TEMPLATES = [
    {
        "stem": "What is 356 + 289?",
        "correct_answer": "A",
        "explanation": "356 + 289 = 645. Add the units (6+9=15, carry 1), then tens (5+8+1=14, carry 1), then hundreds (3+2+1=6).",
        "options": [{"label": "A", "text": "645", "is_correct": True}, {"label": "B", "text": "635", "is_correct": False}, {"label": "C", "text": "545", "is_correct": False}, {"label": "D", "text": "655", "is_correct": False}],
        "subject": "maths", "topic": "Number & Algebra",
    },
    {
        "stem": "Which fraction is equivalent to 3/4?",
        "correct_answer": "B",
        "explanation": "6/8 = (6÷2)/(8÷2) = 3/4. Equivalent fractions are obtained by multiplying or dividing numerator and denominator by the same number.",
        "options": [{"label": "A", "text": "2/3", "is_correct": False}, {"label": "B", "text": "6/8", "is_correct": True}, {"label": "C", "text": "4/5", "is_correct": False}, {"label": "D", "text": "5/6", "is_correct": False}],
        "subject": "maths", "topic": "Number & Algebra",
    },
    {
        "stem": "What is 0.75 × 4?",
        "correct_answer": "C",
        "explanation": "0.75 × 4 = 3.00. Multiply 75 × 4 = 300, then place the decimal: 3.00.",
        "options": [{"label": "A", "text": "2.50", "is_correct": False}, {"label": "B", "text": "2.75", "is_correct": False}, {"label": "C", "text": "3.00", "is_correct": True}, {"label": "D", "text": "3.25", "is_correct": False}],
        "subject": "maths", "topic": "Number & Algebra",
    },
    {
        "stem": "A rectangle has a length of 8 cm and a width of 5 cm. What is its area?",
        "correct_answer": "D",
        "explanation": "Area = length × width = 8 cm × 5 cm = 40 cm².",
        "options": [{"label": "A", "text": "13 cm²", "is_correct": False}, {"label": "B", "text": "26 cm²", "is_correct": False}, {"label": "C", "text": "30 cm²", "is_correct": False}, {"label": "D", "text": "40 cm²", "is_correct": True}],
        "subject": "maths", "topic": "Measurement & Geometry",
    },
    {
        "stem": "What is the value of an angle in an equilateral triangle?",
        "correct_answer": "A",
        "explanation": "An equilateral triangle has three equal angles. Since angles in a triangle sum to 180°, each angle is 180° ÷ 3 = 60°.",
        "options": [{"label": "A", "text": "60°", "is_correct": True}, {"label": "B", "text": "90°", "is_correct": False}, {"label": "C", "text": "45°", "is_correct": False}, {"label": "D", "text": "30°", "is_correct": False}],
        "subject": "maths", "topic": "Measurement & Geometry",
    },
    {
        "stem": "The author's main purpose in an informative text is to:",
        "correct_answer": "B",
        "explanation": "Informative texts are written to provide facts and information to the reader. 'To entertain' describes narrative texts, while 'to persuade' describes persuasive texts.",
        "options": [{"label": "A", "text": "To entertain the reader", "is_correct": False}, {"label": "B", "text": "To provide facts and information", "is_correct": True}, {"label": "C", "text": "To persuade the reader to take action", "is_correct": False}, {"label": "D", "text": "To describe a personal experience", "is_correct": False}],
        "subject": "english", "topic": "Reading Comprehension",
    },
    {
        "stem": "What does the word 'benevolent' most likely mean?",
        "correct_answer": "C",
        "explanation": "'Benevolent' comes from Latin 'bene' (good) + 'volent' (wishing). It means kind and generous. In context, a benevolent person is one who wishes well for others.",
        "options": [{"label": "A", "text": "Angry and hostile", "is_correct": False}, {"label": "B", "text": "Lazy and unmotivated", "is_correct": False}, {"label": "C", "text": "Kind and generous", "is_correct": True}, {"label": "D", "text": "Strict and disciplined", "is_correct": False}],
        "subject": "english", "topic": "Vocabulary",
    },
    {
        "stem": "Look at this pattern: 2, 6, 18, 54, ?. What comes next?",
        "correct_answer": "D",
        "explanation": "Each number is multiplied by 3 to get the next: 2×3=6, 6×3=18, 18×3=54, so 54×3=162.",
        "options": [{"label": "A", "text": "108", "is_correct": False}, {"label": "B", "text": "72", "is_correct": False}, {"label": "C", "text": "216", "is_correct": False}, {"label": "D", "text": "162", "is_correct": True}],
        "subject": "thinking", "topic": "Logical Reasoning",
    },
    {
        "stem": "If all A are B, and all B are C, then:",
        "correct_answer": "A",
        "explanation": "This is a transitive relation. If every A is a member of B, and every B is a member of C, then every A must also be a member of C.",
        "options": [{"label": "A", "text": "All A are C", "is_correct": True}, {"label": "B", "text": "No A are C", "is_correct": False}, {"label": "C", "text": "All C are A", "is_correct": False}, {"label": "D", "text": "Some A are not C", "is_correct": False}],
        "subject": "thinking", "topic": "Logical Reasoning",
    },
    {
        "stem": "A farmer has chickens and cows. There are 20 heads and 56 legs in total. How many cows are there?",
        "correct_answer": "B",
        "explanation": "Let c=chickens, w=cows. c+w=20 (heads). 2c+4w=56 (legs). From first equation: c=20-w. Substitute: 2(20-w)+4w=56 → 40-2w+4w=56 → 40+2w=56 → 2w=16 → w=8. So 8 cows (and 12 chickens).",
        "options": [{"label": "A", "text": "6", "is_correct": False}, {"label": "B", "text": "8", "is_correct": True}, {"label": "C", "text": "10", "is_correct": False}, {"label": "D", "text": "12", "is_correct": False}],
        "subject": "thinking", "topic": "Problem Solving",
    },
    {
        "stem": "The table shows: Mon 12, Tue 18, Wed 15, Thu 22, Fri 20. What was the mean number for the week?",
        "correct_answer": "C",
        "explanation": "Mean = (12+18+15+22+20) ÷ 5 = 87 ÷ 5 = 17.4.",
        "options": [{"label": "A", "text": "18.5", "is_correct": False}, {"label": "B", "text": "20.0", "is_correct": False}, {"label": "C", "text": "17.4", "is_correct": True}, {"label": "D", "text": "15.8", "is_correct": False}],
        "subject": "maths", "topic": "Statistics & Probability",
    },
    {
        "stem": "A train leaves at 9:45 AM and arrives at 11:30 AM. How long was the journey?",
        "correct_answer": "A",
        "explanation": "From 9:45 AM to 11:30 AM: 15 minutes to 10:00 AM, then 1 hour to 11:00 AM, then 30 minutes to 11:30 AM = 1 hour 45 minutes.",
        "options": [{"label": "A", "text": "1 hour 45 minutes", "is_correct": True}, {"label": "B", "text": "2 hours 15 minutes", "is_correct": False}, {"label": "C", "text": "1 hour 15 minutes", "is_correct": False}, {"label": "D", "text": "2 hours 45 minutes", "is_correct": False}],
        "subject": "maths", "topic": "Measurement & Geometry",
    },
]


async def _ensure_questions(
    admin_id: str, subjects: dict, taxonomy: dict, db: AsyncSession,
) -> list[Question]:
    """Create published MCQ questions. Returns question ORM objects."""
    created = []
    for tmpl in _MCQ_TEMPLATES:
        # Check if question already exists by stem
        result = await db.execute(
            select(QuestionVersion).where(QuestionVersion.stem == tmpl["stem"])
        )
        if result.scalar_one_or_none():
            continue

        subject_data = subjects[tmpl["subject"]]
        subject_id = subject_data["obj"].id
        exam_type_id = taxonomy["exam_types"]["oc"].id

        # Find the topic
        topic_id = None
        for t in subject_data["topics"]:
            if t["obj"].name == tmpl["topic"]:
                topic_id = t["obj"].id
                break

        q = Question(
            subject_id=subject_id, exam_type_id=exam_type_id, year_level=5,
            topic_id=topic_id, difficulty=DifficultyLevel.medium,
            question_type=QuestionType.mcq, status=QuestionStatus.published,
            content_ownership=ContentOwnershipType.original,
            source_type="manual", created_by_admin_id=admin_id,
        )
        db.add(q)
        await db.flush()

        v = QuestionVersion(
            question_id=q.id, version_number=1,
            stem=tmpl["stem"], correct_answer=tmpl["correct_answer"],
            full_explanation=tmpl["explanation"], marks=1,
            options_json=tmpl["options"],
            created_by_admin_id=admin_id,
            created_at=datetime.now(tz=timezone.utc),
        )
        db.add(v)
        await db.flush()
        q.current_version_id = v.id
        created.append(q)
        await db.flush()

    await db.commit()
    return created


# ── Pool ─────────────────────────────────────────────────────────────────────


async def _ensure_pool(admin_id: str, questions: list[Question], db: AsyncSession) -> QuestionPool:
    result = await db.execute(select(QuestionPool).where(QuestionPool.name == "OC Maths Practice Pool"))
    pool = result.scalar_one_or_none()
    if not pool:
        pool = QuestionPool(
            name="OC Maths Practice Pool", description="Seed pool for OC Mathematics",
            pool_type=PoolType.static, created_by_admin_id=admin_id,
        )
        db.add(pool)
        await db.flush()
        await db.commit()

    # Add questions to pool if not already members
    for q in questions:
        existing = await db.execute(
            select(QuestionPoolMembership).where(
                QuestionPoolMembership.pool_id == pool.id,
                QuestionPoolMembership.question_id == q.id,
            )
        )
        if not existing.scalar_one_or_none():
            membership = QuestionPoolMembership(
                pool_id=pool.id, question_id=q.id, added_by_admin_id=admin_id,
                added_at=datetime.now(tz=timezone.utc),
            )
            db.add(membership)

    await db.commit()
    return pool


# ── Exam Template + Instance ─────────────────────────────────────────────────


async def _ensure_exam(
    admin_id: str, exam_type_id: str, questions: list[Question], db: AsyncSession,
) -> tuple[ExamInstance, ExamTemplate]:
    result = await db.execute(
        select(ExamTemplate).where(ExamTemplate.title == "Seed OC Maths Practice")
    )
    template = result.scalar_one_or_none()
    if not template:
        template = ExamTemplate(
            title="Seed OC Maths Practice", exam_type_id=exam_type_id,
            duration_minutes=30, status=ExamTemplateStatus.published,
            created_by_admin_id=admin_id,
        )
        db.add(template)
        await db.flush()

    # Create section if needed
    result = await db.execute(
        select(ExamSection).where(ExamSection.exam_template_id == template.id)
    )
    section = result.scalar_one_or_none()
    if not section:
        section = ExamSection(
            exam_template_id=template.id, title="Maths Section",
            order_index=0, instructions="Answer all questions.",
        )
        db.add(section)
        await db.flush()

    # Add questions to section
    for i, q in enumerate(questions):
        if q.exam_type_id != exam_type_id:
            continue
        existing = await db.execute(
            select(ExamSectionQuestion).where(
                ExamSectionQuestion.exam_section_id == section.id,
                ExamSectionQuestion.question_id == q.id,
            )
        )
        if existing.scalar_one_or_none():
            continue
        sq = ExamSectionQuestion(
            exam_section_id=section.id, question_id=q.id,
            order_index=i, marks=1,
        )
        db.add(sq)

    await db.commit()

    # Create or fetch published exam instance
    result = await db.execute(
        select(ExamInstance).where(ExamInstance.title == "Seed OC Maths Practice")
    )
    instance = result.scalar_one_or_none()
    if not instance:
        instance = ExamInstance(
            exam_template_id=template.id, title="Seed OC Maths Practice",
            duration_minutes=30,
        )
        db.add(instance)
        await db.flush()

    # Freeze questions into instance
    existing_frozen = await db.execute(
        select(ExamInstanceQuestion).where(ExamInstanceQuestion.exam_instance_id == instance.id)
    )
    if not existing_frozen.scalar_one_or_none():
        section_questions = (await db.execute(
            select(ExamSectionQuestion)
            .where(ExamSectionQuestion.exam_section_id == section.id)
            .order_by(ExamSectionQuestion.order_index)
        )).scalars().all()

        for idx, sq in enumerate(section_questions):
            q = (await db.execute(select(Question).where(Question.id == sq.question_id))).scalar_one()
            eiq = ExamInstanceQuestion(
                exam_instance_id=instance.id, exam_section_id=section.id,
                question_id=sq.question_id,
                question_version_id=q.current_version_id,
                order_index=idx, marks=sq.marks,
            )
            db.add(eiq)

    # Ensure instance is published
    if instance.status != ExamInstanceStatus.published:
        instance.status = ExamInstanceStatus.published
        instance.published_at = None  # will be set by DB default if needed

    await db.commit()
    return instance, template


# ── Assignment ───────────────────────────────────────────────────────────────


async def _ensure_assignment(
    student: StudentProfile, instance: ExamInstance,
    parent_profile: ParentProfile, db: AsyncSession,
) -> AssignedExam:
    result = await db.execute(
        select(AssignedExam).where(
            AssignedExam.student_id == student.id,
            AssignedExam.exam_instance_id == instance.id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        assignment = AssignedExam(
            student_id=student.id, exam_instance_id=instance.id,
            assigned_by_parent_id=parent_profile.id,
            title_snapshot=instance.title, status=AssignmentStatus.assigned,
        )
        db.add(assignment)
    await db.commit()
    return assignment


# ── Main entry point ─────────────────────────────────────────────────────────


async def seed_all(db: AsyncSession) -> dict:
    """Run all seed steps. Returns a summary dict."""
    summary = {"created": [], "existing": []}

    def _add(created: bool, key: str):
        summary["created" if created else "existing"].append(key)

    # 1. Seed plans (existing seed)
    from app.services.seed_service import seed_plans
    await seed_plans(db)

    # 2. Users
    admin = await _ensure_user(SEED_ADMIN["email"], SEED_ADMIN["password"], UserRole.admin, SEED_ADMIN["name"], db)
    _add(admin.email == SEED_ADMIN["email"], "admin_user")

    parent = await _ensure_user(SEED_PARENT["email"], SEED_PARENT["password"], UserRole.parent, SEED_PARENT["name"], db)
    _add(parent.email == SEED_PARENT["email"], "parent_user")

    parent_profile_result = await db.execute(select(ParentProfile).where(ParentProfile.user_id == parent.id))
    parent_profile = parent_profile_result.scalar_one()

    student = await _ensure_student(SEED_STUDENT["display_name"], SEED_STUDENT["year_level"], SEED_STUDENT["initial_password"], parent_profile.id, parent, db)
    _add(student.display_name == SEED_STUDENT["display_name"], "student")

    # 3. Taxonomy
    taxonomy = await _ensure_taxonomy(db)
    _add(len(taxonomy["exam_types"]) >= 2, "exam_types")
    _add(len(taxonomy["subjects"]) >= 3, "subjects_and_topics")

    # 4. Curriculum
    curriculum = await _ensure_curriculum(db)
    _add(len(curriculum["outcomes"]) >= 5, "curriculum_outcomes")

    # 5. Questions
    admin_profile_result = await db.execute(select(AdminProfile).where(AdminProfile.user_id == admin.id))
    admin_profile = admin_profile_result.scalar_one()
    questions = await _ensure_questions(admin_profile.id, taxonomy["subjects"], taxonomy, db)
    _add(len(questions) >= 10, f"{len(questions)}_questions")

    # 6. Pool
    pool = await _ensure_pool(admin_profile.id, questions, db)
    _add(pool is not None, "question_pool")

    # 7. Exam template + instance
    instance, template = await _ensure_exam(admin_profile.id, taxonomy["exam_types"]["oc"].id, questions, db)
    _add(instance is not None, "exam_instance")

    # 8. Assignment
    assignment = await _ensure_assignment(student, instance, parent_profile, db)
    _add(assignment is not None, "parent_assignment")

    await db.commit()

    summary["accounts"] = {
        "admin": SEED_ADMIN,
        "parent": SEED_PARENT,
        "student": {
            "login_email": "seed01@students.hscai.internal",
            "password": SEED_STUDENT["initial_password"],
            "display_name": SEED_STUDENT["display_name"],
        },
    }
    summary["urls"] = [
        ("Landing", "http://localhost:3090/"),
        ("Login", "http://localhost:3090/login"),
        ("Parent Dashboard", "http://localhost:3090/parent"),
        ("Parent → Student Assignments", "http://localhost:3090/parent/assignments"),
        ("Student Assignments", "http://localhost:3090/me/assignments"),
        ("Available Exams", "http://localhost:3090/exams"),
        ("Student Progress", "http://localhost:3090/me/progress"),
        ("Admin Curriculum", "http://localhost:3090/admin/curriculum"),
    ]

    return summary


async def main():
    async with SessionLocal() as db:
        try:
            result = await seed_all(db)
            print("\n=== Seed Complete ===")
            print(f"Created: {result['created']}")
            print(f"Already existed: {result['existing']}")
            print(f"\nTest Accounts:")
            for role, creds in result["accounts"].items():
                email = creds.get("email") or creds.get("login_email")
                print(f"  {role}: {email} / {creds['password']}")
            print(f"\nTest URLs:")
            for label, url in result["urls"]:
                print(f"  {label}: {url}")
        except Exception as e:
            print(f"Seed error: {e}")
            raise


# Allow running as a module: docker compose exec backend python -m app.seed
if __name__ == "__main__":
    asyncio.run(main())
