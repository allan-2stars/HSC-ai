# Import all models so Alembic and Base.metadata pick them up
from app.models.user import (  # noqa: F401
    AdminProfile,
    ParentProfile,
    RefreshToken,
    StudentProfile,
    User,
)
from app.models.subscription import (  # noqa: F401
    Entitlement,
    Subscription,
    SubscriptionPlan,
)
from app.models.audit import AuditLog  # noqa: F401
from app.models.content import (  # noqa: F401
    ExamType,
    SkillTag,
    Subject,
    Topic,
)
from app.models.question import (  # noqa: F401
    ContentOwnershipType,
    DifficultyLevel,
    MediaType,
    PoolType,
    Question,
    QuestionMedia,
    QuestionPool,
    QuestionPoolMembership,
    QuestionStatus,
    QuestionType,
    QuestionVersion,
    SourceType,
    question_skill_tags,
)
from app.models.exam import (  # noqa: F401
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
from app.models.analytics import (  # noqa: F401
    SkillPerformance,
    TopicPerformance,
)
from app.models.assignment import (  # noqa: F401
    AssignedExam,
    AssignmentStatus,
)
from app.models.curriculum import (  # noqa: F401
    CurriculumFramework,
    CurriculumOutcome,
    QuestionOutcomeMapping,
)
from app.models.import_job import (  # noqa: F401
    ImportJob,
    ImportJobStatus,
)
from app.models.ocr_job import (  # noqa: F401
    OCRJob,
    OCRJobStatus,
    OCRPageResult,
)
from app.models.ai_job import (  # noqa: F401
    AIGenerationJob,
    AIGenerationJobStatus,
)
from app.models.quality import (  # noqa: F401
    QuestionQualityReview,
)
from app.models.writing import (  # noqa: F401
    WritingSubmission,
    WritingSubmissionStatus,
    WritingTask,
    WritingTaskStatus,
)
