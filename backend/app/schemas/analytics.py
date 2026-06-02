from pydantic import BaseModel


# ── Summary ──────────────────────────────────────────────────────────────────

class StudentSummaryResponse(BaseModel):
    total_attempts: int
    average_score: float
    best_score: float
    latest_score: float
    total_questions_answered: int
    total_correct_answers: int
    overall_accuracy: float


# ── Topic Performance ────────────────────────────────────────────────────────

class TopicPerformanceItem(BaseModel):
    topic_id: str
    topic_name: str
    attempts: int
    correct_count: int
    accuracy_rate: float
    average_time_seconds: float = 0.0


class TopicPerformanceResponse(BaseModel):
    topics: list[TopicPerformanceItem]


# ── Skill Performance ────────────────────────────────────────────────────────

class SkillPerformanceItem(BaseModel):
    skill_id: str
    skill_name: str
    attempts: int
    correct_count: int
    accuracy_rate: float
    average_time_seconds: float = 0.0


class SkillPerformanceResponse(BaseModel):
    skills: list[SkillPerformanceItem]


# ── Recommendations ──────────────────────────────────────────────────────────

class WeakStrongItem(BaseModel):
    id: str
    name: str
    accuracy_rate: float
    attempts: int


class RecommendationItem(BaseModel):
    type: str
    target_id: str
    target_name: str
    message: str


class SlowTopicItem(BaseModel):
    id: str
    name: str
    average_time_seconds: float
    attempts: int


class RecommendationsResponse(BaseModel):
    weak_topics: list[WeakStrongItem]
    strong_topics: list[WeakStrongItem]
    weak_skills: list[WeakStrongItem]
    strong_skills: list[WeakStrongItem]
    slow_topics: list[SlowTopicItem] = []
    recommendations: list[RecommendationItem]


# ── Progress (student self-view) ─────────────────────────────────────────────

class StudentProgressResponse(BaseModel):
    summary: StudentSummaryResponse
    weak_topics: list[WeakStrongItem]
    strong_topics: list[WeakStrongItem]
    weak_skills: list[WeakStrongItem]
    strong_skills: list[WeakStrongItem]
    slow_topics: list[SlowTopicItem] = []


# ── Trend ────────────────────────────────────────────────────────────────────

class TrendItem(BaseModel):
    completed_at: str
    score_percent: float
    exam_title: str


# ── Exam History ─────────────────────────────────────────────────────────────

class ExamHistoryItem(BaseModel):
    attempt_id: str
    exam_title: str
    status: str
    score_percent: float | None
    total_questions: int
    correct_count: int | None
    completed_at: str | None

    model_config = {"from_attributes": True}
