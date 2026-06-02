from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analytics import SkillPerformance, TopicPerformance
from app.models.content import SkillTag, Topic
from app.models.exam import Attempt, AttemptAnswer, AttemptStatus, ExamInstanceQuestion
from app.models.question import Question, question_skill_tags


# ── Thresholds ───────────────────────────────────────────────────────────────

_WEAKNESS_THRESHOLD = 60.0   # accuracy < 60% → weakness
_STRENGTH_THRESHOLD = 85.0   # accuracy > 85% → strength
_SLOW_TIME_SECONDS = 90.0     # average_time > 90s → slow


# ── Summary ──────────────────────────────────────────────────────────────────

async def calculate_student_summary(
    student_id: str, db: AsyncSession
) -> dict:
    """Calculate overall performance summary for a student."""
    result = await db.execute(
        select(Attempt)
        .where(
            Attempt.student_id == student_id,
            Attempt.status.in_([AttemptStatus.submitted, AttemptStatus.expired]),
        )
        .order_by(Attempt.submitted_at.desc())
    )
    attempts = list(result.scalars().all())

    if not attempts:
        return {
            "total_attempts": 0,
            "average_score": 0.0,
            "best_score": 0.0,
            "latest_score": 0.0,
            "total_questions_answered": 0,
            "total_correct_answers": 0,
            "overall_accuracy": 0.0,
        }

    total_attempts = len(attempts)
    scores = [a.score_percent for a in attempts if a.score_percent is not None]
    average_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    best_score = max(scores) if scores else 0.0
    latest_score = scores[0] if scores else 0.0

    total_questions = sum(a.total_questions for a in attempts)
    total_correct = sum(a.correct_count for a in attempts if a.correct_count is not None)
    overall_accuracy = round((total_correct / total_questions) * 100, 1) if total_questions > 0 else 0.0

    return {
        "total_attempts": total_attempts,
        "average_score": average_score,
        "best_score": best_score,
        "latest_score": latest_score,
        "total_questions_answered": total_questions,
        "total_correct_answers": total_correct,
        "overall_accuracy": overall_accuracy,
    }


# ── Trend ────────────────────────────────────────────────────────────────────

async def calculate_trend(
    student_id: str, db: AsyncSession, limit: int = 20
) -> list[dict]:
    """Return score trend: completed_at, score_percent, exam_title, oldest → newest."""
    result = await db.execute(
        select(Attempt)
        .options(selectinload(Attempt.exam_instance))
        .where(
            Attempt.student_id == student_id,
            Attempt.status.in_([AttemptStatus.submitted, AttemptStatus.expired]),
        )
        .order_by(Attempt.submitted_at.asc())
        .limit(limit)
    )
    attempts = list(result.scalars().all())
    return [
        {
            "completed_at": a.submitted_at.isoformat() if a.submitted_at else a.started_at.isoformat(),
            "score_percent": a.score_percent or 0.0,
            "exam_title": a.exam_instance.title,
        }
        for a in attempts if a.submitted_at
    ]


# ── Topic Performance ────────────────────────────────────────────────────────

async def calculate_topic_performance(
    student_id: str, db: AsyncSession
) -> list[dict]:
    """Calculate per-topic performance by aggregating attempt answer data."""
    # Get all submitted/expired attempts for this student
    result = await db.execute(
        select(Attempt)
        .options(selectinload(Attempt.answers).selectinload(AttemptAnswer.exam_instance_question))
        .where(
            Attempt.student_id == student_id,
            Attempt.status.in_([AttemptStatus.submitted, AttemptStatus.expired]),
        )
    )
    attempts = list(result.scalars().all())

    if not attempts:
        return []

    # Collect all answered questions with their question_ids and time
    qa_pairs: list[tuple[str, bool, int]] = []  # (question_id, is_correct, time_spent_seconds)
    for attempt in attempts:
        for answer in attempt.answers:
            eiq = answer.exam_instance_question
            if eiq and answer.is_correct is not None:
                qa_pairs.append((eiq.question_id, answer.is_correct, answer.time_spent_seconds))

    if not qa_pairs:
        return []

    # Get topic assignments for all relevant questions at once
    question_ids = list({qid for qid, _, _ in qa_pairs})
    result = await db.execute(
        select(Question.id, Question.topic_id).where(Question.id.in_(question_ids))
    )
    question_topics = {row[0]: row[1] for row in result.fetchall()}

    # Aggregate by topic
    topic_stats: dict[str, dict] = {}
    for qid, is_correct, time_spent in qa_pairs:
        topic_id = question_topics.get(qid)
        if not topic_id:
            continue
        if topic_id not in topic_stats:
            topic_stats[topic_id] = {"attempts": 0, "correct": 0, "total_time": 0}
        topic_stats[topic_id]["attempts"] += 1
        topic_stats[topic_id]["total_time"] += time_spent
        if is_correct:
            topic_stats[topic_id]["correct"] += 1

    # Get topic names
    topic_ids = list(topic_stats.keys())
    result = await db.execute(select(Topic).where(Topic.id.in_(topic_ids)))
    topic_map = {t.id: t for t in result.scalars().all()}

    output = []
    for topic_id, stats in topic_stats.items():
        accuracy = round((stats["correct"] / stats["attempts"]) * 100, 1)
        avg_time = round(stats["total_time"] / stats["attempts"], 1)
        topic = topic_map.get(topic_id)
        output.append({
            "topic_id": topic_id,
            "topic_name": topic.name if topic else "Unknown",
            "attempts": stats["attempts"],
            "correct_count": stats["correct"],
            "accuracy_rate": accuracy,
            "average_time_seconds": avg_time,
        })

    output.sort(key=lambda x: x["accuracy_rate"])
    return output


# ── Skill Performance ────────────────────────────────────────────────────────

async def calculate_skill_performance(
    student_id: str, db: AsyncSession
) -> list[dict]:
    """Calculate per-skill performance by aggregating attempt answer data."""
    result = await db.execute(
        select(Attempt)
        .options(selectinload(Attempt.answers).selectinload(AttemptAnswer.exam_instance_question))
        .where(
            Attempt.student_id == student_id,
            Attempt.status.in_([AttemptStatus.submitted, AttemptStatus.expired]),
        )
    )
    attempts = list(result.scalars().all())

    if not attempts:
        return []

    qa_pairs: list[tuple[str, bool, int]] = []
    for attempt in attempts:
        for answer in attempt.answers:
            eiq = answer.exam_instance_question
            if eiq and answer.is_correct is not None:
                qa_pairs.append((eiq.question_id, answer.is_correct, answer.time_spent_seconds))

    if not qa_pairs:
        return []

    question_ids = list({qid for qid, _, _ in qa_pairs})

    # Get skill tag mappings for all questions
    result = await db.execute(
        select(question_skill_tags.c.question_id, question_skill_tags.c.skill_tag_id)
        .where(question_skill_tags.c.question_id.in_(question_ids))
    )
    qst_rows = result.fetchall()

    # Build question → skill_tags map
    q_to_skills: dict[str, list[str]] = {}
    skill_ids: set[str] = set()
    for qid, st_id in qst_rows:
        q_to_skills.setdefault(qid, []).append(st_id)
        skill_ids.add(st_id)

    if not skill_ids:
        return []

    # Aggregate by skill
    skill_stats: dict[str, dict] = {}
    for qid, is_correct, time_spent in qa_pairs:
        for st_id in q_to_skills.get(qid, []):
            if st_id not in skill_stats:
                skill_stats[st_id] = {"attempts": 0, "correct": 0, "total_time": 0}
            skill_stats[st_id]["attempts"] += 1
            skill_stats[st_id]["total_time"] += time_spent
            if is_correct:
                skill_stats[st_id]["correct"] += 1

    # Get skill names
    result = await db.execute(select(SkillTag).where(SkillTag.id.in_(list(skill_ids))))
    skill_map = {s.id: s for s in result.scalars().all()}

    output = []
    for skill_id, stats in skill_stats.items():
        accuracy = round((stats["correct"] / stats["attempts"]) * 100, 1)
        avg_time = round(stats["total_time"] / stats["attempts"], 1)
        skill = skill_map.get(skill_id)
        output.append({
            "skill_id": skill_id,
            "skill_name": skill.name if skill else "Unknown",
            "attempts": stats["attempts"],
            "correct_count": stats["correct"],
            "accuracy_rate": accuracy,
            "average_time_seconds": avg_time,
        })

    output.sort(key=lambda x: x["accuracy_rate"])
    return output


# ── Weakness / Strength Detection ────────────────────────────────────────────

async def get_recommendations(
    student_id: str, db: AsyncSession
) -> dict:
    """Rule-based weakness/strength detection from topic and skill data."""
    topics = await calculate_topic_performance(student_id, db)
    skills = await calculate_skill_performance(student_id, db)

    weak_topics = [
        {"topic_id": t["topic_id"], "topic_name": t["topic_name"],
         "accuracy_rate": t["accuracy_rate"], "attempts": t["attempts"]}
        for t in topics if t["accuracy_rate"] < _WEAKNESS_THRESHOLD and t["attempts"] >= 2
    ]
    strong_topics = [
        {"topic_id": t["topic_id"], "topic_name": t["topic_name"],
         "accuracy_rate": t["accuracy_rate"], "attempts": t["attempts"]}
        for t in topics if t["accuracy_rate"] > _STRENGTH_THRESHOLD and t["attempts"] >= 2
    ]
    weak_skills = [
        {"skill_id": s["skill_id"], "skill_name": s["skill_name"],
         "accuracy_rate": s["accuracy_rate"], "attempts": s["attempts"]}
        for s in skills if s["accuracy_rate"] < _WEAKNESS_THRESHOLD and s["attempts"] >= 2
    ]
    strong_skills = [
        {"skill_id": s["skill_id"], "skill_name": s["skill_name"],
         "accuracy_rate": s["accuracy_rate"], "attempts": s["attempts"]}
        for s in skills if s["accuracy_rate"] > _STRENGTH_THRESHOLD and s["attempts"] >= 2
    ]

    slow_topics = [
        {"topic_id": t["topic_id"], "topic_name": t["topic_name"],
         "average_time_seconds": t["average_time_seconds"], "attempts": t["attempts"]}
        for t in topics if t["average_time_seconds"] > _SLOW_TIME_SECONDS and t["attempts"] >= 2
    ]

    recommendations = _generate_recommendations(weak_topics, weak_skills, slow_topics)

    return {
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "weak_skills": weak_skills,
        "strong_skills": strong_skills,
        "slow_topics": slow_topics,
        "recommendations": recommendations,
    }


def _generate_recommendations(
    weak_topics: list[dict], weak_skills: list[dict], slow_topics: list[dict]
) -> list[dict]:
    """Generate rule-based text recommendations from weaknesses and slow topics."""
    recs = []
    for t in weak_topics[:5]:
        recs.append({
            "type": "topic",
            "target_id": t["topic_id"],
            "target_name": t["topic_name"],
            "message": (
                f"{t['topic_name']} accuracy is {t['accuracy_rate']}%. "
                f"Focus on more {t['topic_name']} practice questions."
            ),
        })
    for t in slow_topics[:5]:
        recs.append({
            "type": "slow_topic",
            "target_id": t["topic_id"],
            "target_name": t["topic_name"],
            "message": (
                f"{t['topic_name']} average solve time is {t['average_time_seconds']} seconds. "
                f"Consider working on speed in {t['topic_name']}."
            ),
        })
    for s in weak_skills[:5]:
        recs.append({
            "type": "skill",
            "target_id": s["skill_id"],
            "target_name": s["skill_name"],
            "message": (
                f"{s['skill_name']} accuracy is {s['accuracy_rate']}%. "
                f"Practice more {s['skill_name']} questions to improve."
            ),
        })
    return recs
