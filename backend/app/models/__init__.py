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
