# Question Bank Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Question Bank Foundation (Phase 3): taxonomy tables (Subject, ExamType, Topic, SkillTag), Question/QuestionVersion/QuestionMedia models with full content lifecycle, publishing constraint enforcement, and admin CRUD APIs for all content types.

**Architecture:** Five new SQLAlchemy models split across two files (`content.py` for taxonomy, `question.py` for questions/pools). Services handle business logic including status transition validation and the publish-block rule for restricted ownership. Admin-only REST endpoints under `/api/v1/admin/` wire services to HTTP. Tests use the existing sync TestClient + async DB fixture pattern.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async mapped columns), Pydantic v2, Alembic, PostgreSQL, pytest with TestClient

---

## File Map

**New files:**
- `backend/app/models/content.py` — Subject, ExamType, Topic, SkillTag
- `backend/app/models/question.py` — Question, QuestionVersion, QuestionMedia, QuestionPool, QuestionPoolMembership + all enums
- `backend/app/schemas/content.py` — Pydantic request/response schemas for taxonomy
- `backend/app/schemas/question.py` — Pydantic request/response schemas for questions/versions/pools
- `backend/app/services/content_service.py` — Taxonomy CRUD
- `backend/app/services/question_service.py` — Question lifecycle, versioning, pool management
- `backend/app/api/v1/admin/__init__.py` — empty init
- `backend/app/api/v1/admin/content.py` — taxonomy admin endpoints
- `backend/app/api/v1/admin/questions.py` — question admin endpoints
- `backend/app/api/v1/admin/pools.py` — pool admin endpoints
- `backend/tests/test_admin_content.py` — taxonomy API tests
- `backend/tests/test_admin_questions.py` — question API tests
- `backend/tests/test_admin_pools.py` — pool API tests

**Modified files:**
- `backend/app/models/__init__.py` — add content + question imports
- `backend/app/core/deps.py` — add `get_current_admin_profile` dependency
- `backend/app/api/v1/router.py` — include admin sub-routers
- `backend/tests/conftest.py` — add `create_admin_and_login` helper

---

## Task 1: Taxonomy DB Models

**Files:**
- Create: `backend/app/models/content.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write taxonomy models**

Create `backend/app/models/content.py`:

```python
import enum
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    topics: Mapped[list["Topic"]] = relationship(back_populates="subject")


class ExamType(Base, TimestampMixin):
    __tablename__ = "exam_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="topics")


class SkillTag(Base, TimestampMixin):
    __tablename__ = "skill_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subject: Mapped["Subject | None"] = relationship()
```

- [ ] **Step 2: Register taxonomy models with Base.metadata**

Edit `backend/app/models/__init__.py` — append these imports after the existing ones:

```python
from app.models.content import (  # noqa: F401
    ExamType,
    SkillTag,
    Subject,
    Topic,
)
```

- [ ] **Step 3: Verify no import errors**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/python -c "import app.models; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run existing tests to confirm nothing broken**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/ -q --tb=short
```

Expected: all 36 tests still pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/content.py backend/app/models/__init__.py
git commit -m "feat(m2): add taxonomy DB models (Subject, ExamType, Topic, SkillTag)"
```

---

## Task 2: Question DB Models

**Files:**
- Create: `backend/app/models/question.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write question models**

Create `backend/app/models/question.py`:

```python
import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DifficultyLevel(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class QuestionType(str, enum.Enum):
    mcq = "mcq"
    short_answer = "short_answer"
    extended_response = "extended_response"


class QuestionStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    approved = "approved"
    published = "published"
    archived = "archived"
    rejected = "rejected"


class SourceType(str, enum.Enum):
    manual = "manual"
    ocr = "ocr"
    ai = "ai"


class ContentOwnershipType(str, enum.Enum):
    original = "original"
    licensed = "licensed"
    public_domain = "public_domain"
    approved_internal = "approved_internal"
    user_provided_with_rights = "user_provided_with_rights"
    internal_draft = "internal_draft"
    restricted_reference_only = "restricted_reference_only"


class MediaType(str, enum.Enum):
    image = "image"
    audio = "audio"


class PoolType(str, enum.Enum):
    static = "static"
    dynamic = "dynamic"


question_skill_tags = Table(
    "question_skill_tags",
    Base.metadata,
    Column(
        "question_id",
        String(36),
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_tag_id",
        String(36),
        ForeignKey("skill_tags.id"),
        primary_key=True,
    ),
)


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=False, index=True
    )
    exam_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=False, index=True
    )
    year_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("topics.id"), nullable=True
    )
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        SAEnum(DifficultyLevel, name="difficulty_level"), nullable=False
    )
    question_type: Mapped[QuestionType] = mapped_column(
        SAEnum(QuestionType, name="question_type_enum"), nullable=False
    )
    status: Mapped[QuestionStatus] = mapped_column(
        SAEnum(QuestionStatus, name="question_status"),
        default=QuestionStatus.draft,
        nullable=False,
        index=True,
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type"), nullable=False
    )
    content_ownership: Mapped[ContentOwnershipType] = mapped_column(
        SAEnum(ContentOwnershipType, name="content_ownership_type"), nullable=False
    )
    copyright_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # use_alter=True defers this FK until after question_versions table is created.
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "question_versions.id",
            use_alter=True,
            name="fk_question_current_version_id",
        ),
        nullable=True,
    )
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )

    current_version: Mapped["QuestionVersion | None"] = relationship(
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions: Mapped[list["QuestionVersion"]] = relationship(
        back_populates="question",
        foreign_keys="[QuestionVersion.question_id]",
        order_by="QuestionVersion.version_number",
    )
    skill_tags: Mapped[list["SkillTag"]] = relationship(  # type: ignore[name-defined]
        secondary=question_skill_tags
    )
    created_by_admin: Mapped["AdminProfile"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[created_by_admin_id]
    )


class QuestionVersion(Base):
    __tablename__ = "question_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    marks: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    options_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    question: Mapped["Question"] = relationship(
        back_populates="versions", foreign_keys=[question_id]
    )
    media: Mapped[list["QuestionMedia"]] = relationship(
        back_populates="question_version", order_by="QuestionMedia.sort_order"
    )


class QuestionMedia(Base):
    __tablename__ = "question_media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("question_versions.id"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(
        SAEnum(MediaType, name="media_type"), nullable=False
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    question_version: Mapped["QuestionVersion"] = relationship(back_populates="media")


class QuestionPool(Base, TimestampMixin):
    __tablename__ = "question_pools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=True
    )
    exam_type_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=True
    )
    year_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pool_type: Mapped[PoolType] = mapped_column(
        SAEnum(PoolType, name="pool_type"), default=PoolType.static, nullable=False
    )
    query_criteria_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )

    memberships: Mapped[list["QuestionPoolMembership"]] = relationship(back_populates="pool")


class QuestionPoolMembership(Base):
    __tablename__ = "question_pool_memberships"

    pool_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("question_pools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    added_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )

    pool: Mapped["QuestionPool"] = relationship(back_populates="memberships")
    question: Mapped["Question"] = relationship()
```

- [ ] **Step 2: Register question models with Base.metadata**

Append to `backend/app/models/__init__.py`:

```python
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
```

- [ ] **Step 3: Verify no import errors**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/python -c "import app.models; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run existing tests**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/ -q --tb=short
```

Expected: all 36 pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/question.py backend/app/models/__init__.py
git commit -m "feat(m2): add Question/QuestionVersion/QuestionPool DB models"
```

---

## Task 3: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/<hash>_question_bank_foundation.py` (auto-generated)

This migration adds all new tables to the production/dev database. Tests use `Base.metadata.create_all()` and pick up the new models automatically — this migration is only needed for the Docker DB.

- [ ] **Step 1: Generate migration inside the backend container**

```bash
docker exec hscai-backend alembic revision --autogenerate -m "question_bank_foundation"
```

Expected output: `Generating .../alembic/versions/<hash>_question_bank_foundation.py ... done`

If the container isn't running, start it first:
```bash
cd /home/pi/HSC-ai && docker compose up -d db backend
# Wait ~5s for services to be healthy, then retry the alembic command
```

- [ ] **Step 2: Review the generated migration**

```bash
cat /home/pi/HSC-ai/backend/alembic/versions/*question_bank_foundation.py
```

Confirm it contains `create_table` calls for:
- `subjects`, `exam_types`, `topics`, `skill_tags`
- `questions`, `question_versions`, `question_media`
- `question_skill_tags`, `question_pools`, `question_pool_memberships`

Also confirm an `ALTER TABLE` statement for the circular FK `fk_question_current_version_id` appears at the end of `upgrade()`.

- [ ] **Step 3: Apply migration**

```bash
docker exec hscai-backend alembic upgrade head
```

Expected: `Running upgrade b6a41ed04bcd -> <newhash>, question_bank_foundation`

- [ ] **Step 4: Verify tables exist**

```bash
docker exec hscai-db psql -U hscai -d hscai -c "\dt" | grep -E "subjects|exam_types|topics|skill_tags|questions|question_"
```

Expected: all 9 new tables listed.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(m2): Alembic migration — question bank foundation tables"
```

---

## Task 4: Admin Test Fixture + Admin Profile Dependency

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/app/core/deps.py`

- [ ] **Step 1: Add `create_admin_and_login` helper to conftest**

In `backend/tests/conftest.py`, after the existing `auth_headers` function, add:

```python
def create_admin_and_login(
    client: TestClient,
    email: str = "admin@test.com",
    password: str = "AdminPass123",
) -> dict:
    """Create an admin user directly in the test DB, then login to get tokens."""
    async def _seed():
        async with _SessionFactory() as session:
            from app.core.security import hash_password
            from app.models.user import AdminProfile, User, UserRole
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=UserRole.admin,
            )
            session.add(user)
            await session.flush()
            profile = AdminProfile(user_id=user.id, display_name="Test Admin")
            session.add(profile)
            await session.commit()

    _run(_seed())
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()
```

- [ ] **Step 2: Add `get_current_admin_profile` dependency to deps.py**

In `backend/app/core/deps.py`, after the `get_current_admin` function, add:

```python
from sqlalchemy import select

from app.models.user import AdminProfile


async def get_current_admin_profile(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminProfile:
    result = await db.execute(select(AdminProfile).where(AdminProfile.user_id == admin.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=500, detail="Admin profile not found")
    return profile
```

Note: `select` and `AdminProfile` may already be imported; add only what's missing.

- [ ] **Step 3: Verify the helper works by writing a quick test**

Create a temporary inline check (run and then discard):

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/python -c "
import os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://hscai:change_me_in_production@localhost:5435/hscai'
os.environ['REDIS_URL'] = 'redis://localhost:6380/0'
from tests.conftest import create_admin_and_login
print('import OK')
"
```

Expected: `import OK`

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py backend/app/core/deps.py
git commit -m "feat(m2): add admin test fixture and get_current_admin_profile dep"
```

---

## Task 5: Taxonomy Schemas and Service

**Files:**
- Create: `backend/app/schemas/content.py`
- Create: `backend/app/services/content_service.py`

- [ ] **Step 1: Write taxonomy Pydantic schemas**

Create `backend/app/schemas/content.py`:

```python
from pydantic import BaseModel, field_validator


class SubjectCreateRequest(BaseModel):
    code: str
    name: str

    @field_validator("code")
    @classmethod
    def code_nonempty(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("code cannot be empty")
        return v

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class SubjectUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class SubjectResponse(BaseModel):
    id: str
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class ExamTypeCreateRequest(BaseModel):
    code: str
    name: str

    @field_validator("code")
    @classmethod
    def code_nonempty(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("code cannot be empty")
        return v

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class ExamTypeUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class ExamTypeResponse(BaseModel):
    id: str
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class TopicCreateRequest(BaseModel):
    subject_id: str
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class TopicUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class TopicResponse(BaseModel):
    id: str
    subject_id: str
    name: str
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class SkillTagCreateRequest(BaseModel):
    name: str
    subject_id: str | None = None

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class SkillTagUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class SkillTagResponse(BaseModel):
    id: str
    name: str
    subject_id: str | None
    is_active: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write taxonomy service**

Create `backend/app/services/content_service.py`:

```python
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ExamType, SkillTag, Subject, Topic


# ── Subject ──────────────────────────────────────────────────────────────────

async def create_subject(code: str, name: str, db: AsyncSession) -> Subject:
    existing = await db.execute(select(Subject).where(Subject.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subject code already exists")
    subject = Subject(code=code, name=name)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


async def list_subjects(db: AsyncSession) -> list[Subject]:
    result = await db.execute(select(Subject).where(Subject.is_active == True).order_by(Subject.name))  # noqa: E712
    return list(result.scalars().all())


async def get_subject(subject_id: str, db: AsyncSession) -> Subject:
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


async def update_subject(
    subject_id: str, name: str | None, is_active: bool | None, db: AsyncSession
) -> Subject:
    subject = await get_subject(subject_id, db)
    if name is not None:
        subject.name = name
    if is_active is not None:
        subject.is_active = is_active
    await db.commit()
    await db.refresh(subject)
    return subject


# ── ExamType ─────────────────────────────────────────────────────────────────

async def create_exam_type(code: str, name: str, db: AsyncSession) -> ExamType:
    existing = await db.execute(select(ExamType).where(ExamType.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ExamType code already exists")
    exam_type = ExamType(code=code, name=name)
    db.add(exam_type)
    await db.commit()
    await db.refresh(exam_type)
    return exam_type


async def list_exam_types(db: AsyncSession) -> list[ExamType]:
    result = await db.execute(select(ExamType).where(ExamType.is_active == True).order_by(ExamType.name))  # noqa: E712
    return list(result.scalars().all())


async def get_exam_type(exam_type_id: str, db: AsyncSession) -> ExamType:
    result = await db.execute(select(ExamType).where(ExamType.id == exam_type_id))
    exam_type = result.scalar_one_or_none()
    if not exam_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ExamType not found")
    return exam_type


async def update_exam_type(
    exam_type_id: str, name: str | None, is_active: bool | None, db: AsyncSession
) -> ExamType:
    exam_type = await get_exam_type(exam_type_id, db)
    if name is not None:
        exam_type.name = name
    if is_active is not None:
        exam_type.is_active = is_active
    await db.commit()
    await db.refresh(exam_type)
    return exam_type


# ── Topic ────────────────────────────────────────────────────────────────────

async def create_topic(
    subject_id: str, name: str, description: str | None, db: AsyncSession
) -> Topic:
    # Verify subject exists
    await get_subject(subject_id, db)
    topic = Topic(subject_id=subject_id, name=name, description=description)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


async def list_topics(db: AsyncSession, subject_id: str | None = None) -> list[Topic]:
    query = select(Topic).where(Topic.is_active == True)  # noqa: E712
    if subject_id:
        query = query.where(Topic.subject_id == subject_id)
    result = await db.execute(query.order_by(Topic.name))
    return list(result.scalars().all())


async def get_topic(topic_id: str, db: AsyncSession) -> Topic:
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return topic


async def update_topic(
    topic_id: str,
    name: str | None,
    description: str | None,
    is_active: bool | None,
    db: AsyncSession,
) -> Topic:
    topic = await get_topic(topic_id, db)
    if name is not None:
        topic.name = name
    if description is not None:
        topic.description = description
    if is_active is not None:
        topic.is_active = is_active
    await db.commit()
    await db.refresh(topic)
    return topic


# ── SkillTag ─────────────────────────────────────────────────────────────────

async def create_skill_tag(
    name: str, subject_id: str | None, db: AsyncSession
) -> SkillTag:
    tag = SkillTag(name=name, subject_id=subject_id)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def list_skill_tags(db: AsyncSession) -> list[SkillTag]:
    result = await db.execute(
        select(SkillTag).where(SkillTag.is_active == True).order_by(SkillTag.name)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_skill_tag(skill_tag_id: str, db: AsyncSession) -> SkillTag:
    result = await db.execute(select(SkillTag).where(SkillTag.id == skill_tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SkillTag not found")
    return tag


async def update_skill_tag(
    skill_tag_id: str, name: str | None, is_active: bool | None, db: AsyncSession
) -> SkillTag:
    tag = await get_skill_tag(skill_tag_id, db)
    if name is not None:
        tag.name = name
    if is_active is not None:
        tag.is_active = is_active
    await db.commit()
    await db.refresh(tag)
    return tag
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/content.py backend/app/services/content_service.py
git commit -m "feat(m2): taxonomy schemas and service"
```

---

## Task 6: Taxonomy Admin API + Tests

**Files:**
- Create: `backend/app/api/v1/admin/__init__.py`
- Create: `backend/app/api/v1/admin/content.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/test_admin_content.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin_content.py`:

```python
from fastapi.testclient import TestClient

from tests.conftest import auth_headers, create_admin_and_login, register_parent


def test_admin_can_create_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "maths"
    assert data["name"] == "Mathematics"
    assert data["is_active"] is True
    assert "id" in data


def test_non_admin_cannot_create_subject(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_unauthenticated_cannot_create_subject(client: TestClient):
    resp = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"})
    assert resp.status_code == 401


def test_duplicate_subject_code_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    )
    resp = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Maths Duplicate"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_admin_can_list_subjects(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Mathematics"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/subjects", json={"code": "english", "name": "English"}, headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/subjects", headers=auth_headers(tokens))
    assert resp.status_code == 200
    codes = {s["code"] for s in resp.json()}
    assert codes == {"maths", "english"}


def test_admin_can_get_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    created = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    resp = client.get(f"/api/v1/admin/subjects/{created['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_admin_can_update_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    created = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    resp = client.patch(
        f"/api/v1/admin/subjects/{created['id']}",
        json={"name": "Mathematics Updated"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Mathematics Updated"


def test_admin_can_create_exam_type(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/exam-types",
        json={"code": "oc", "name": "Opportunity Class"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "oc"


def test_duplicate_exam_type_code_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/exam-types", json={"code": "oc", "name": "OC"}, headers=auth_headers(tokens))
    resp = client.post("/api/v1/admin/exam-types", json={"code": "oc", "name": "OC2"}, headers=auth_headers(tokens))
    assert resp.status_code == 409


def test_admin_can_list_exam_types(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/exam-types", json={"code": "oc", "name": "OC"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/exam-types", json={"code": "selective", "name": "Selective"}, headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/exam-types", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_admin_can_create_topic(client: TestClient):
    tokens = create_admin_and_login(client)
    subj = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    resp = client.post(
        "/api/v1/admin/topics",
        json={"subject_id": subj["id"], "name": "Fractions"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Fractions"
    assert resp.json()["subject_id"] == subj["id"]


def test_topic_requires_valid_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/topics",
        json={"subject_id": "nonexistent-id", "name": "Fractions"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


def test_admin_can_list_topics_by_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    subj = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    client.post("/api/v1/admin/topics", json={"subject_id": subj["id"], "name": "Fractions"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/topics", json={"subject_id": subj["id"], "name": "Decimals"}, headers=auth_headers(tokens))
    resp = client.get(f"/api/v1/admin/topics?subject_id={subj['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_admin_can_create_skill_tag(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/skill-tags",
        json={"name": "Pattern Recognition"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Pattern Recognition"
    assert resp.json()["subject_id"] is None


def test_admin_can_create_skill_tag_with_subject(client: TestClient):
    tokens = create_admin_and_login(client)
    subj = client.post("/api/v1/admin/subjects", json={"code": "maths", "name": "Maths"}, headers=auth_headers(tokens)).json()
    resp = client.post(
        "/api/v1/admin/skill-tags",
        json={"name": "Arithmetic", "subject_id": subj["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["subject_id"] == subj["id"]


def test_admin_can_list_skill_tags(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/skill-tags", json={"name": "Tag A"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/skill-tags", json={"name": "Tag B"}, headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/skill-tags", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2
```

- [ ] **Step 2: Run tests to confirm they fail (routes don't exist yet)**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/test_admin_content.py -q --tb=line 2>&1 | head -20
```

Expected: failures with `404` (routes not registered yet).

- [ ] **Step 3: Create admin package and content router**

Create `backend/app/api/v1/admin/__init__.py` (empty file):
```python
```

Create `backend/app/api/v1/admin/content.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import AdminProfile, User
from app.schemas.content import (
    ExamTypeCreateRequest,
    ExamTypeResponse,
    ExamTypeUpdateRequest,
    SkillTagCreateRequest,
    SkillTagResponse,
    SkillTagUpdateRequest,
    SubjectCreateRequest,
    SubjectResponse,
    SubjectUpdateRequest,
    TopicCreateRequest,
    TopicResponse,
    TopicUpdateRequest,
)
from app.services import content_service

router = APIRouter(prefix="/admin", tags=["admin-content"])


# ── Subjects ─────────────────────────────────────────────────────────────────

@router.post("/subjects", response_model=SubjectResponse, status_code=201)
async def create_subject(
    body: SubjectCreateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.create_subject(code=body.code, name=body.name, db=db)


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.list_subjects(db=db)


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.get_subject(subject_id=subject_id, db=db)


@router.patch("/subjects/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    body: SubjectUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.update_subject(
        subject_id=subject_id, name=body.name, is_active=body.is_active, db=db
    )


# ── ExamTypes ─────────────────────────────────────────────────────────────────

@router.post("/exam-types", response_model=ExamTypeResponse, status_code=201)
async def create_exam_type(
    body: ExamTypeCreateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.create_exam_type(code=body.code, name=body.name, db=db)


@router.get("/exam-types", response_model=list[ExamTypeResponse])
async def list_exam_types(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.list_exam_types(db=db)


@router.get("/exam-types/{exam_type_id}", response_model=ExamTypeResponse)
async def get_exam_type(
    exam_type_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.get_exam_type(exam_type_id=exam_type_id, db=db)


@router.patch("/exam-types/{exam_type_id}", response_model=ExamTypeResponse)
async def update_exam_type(
    exam_type_id: str,
    body: ExamTypeUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.update_exam_type(
        exam_type_id=exam_type_id, name=body.name, is_active=body.is_active, db=db
    )


# ── Topics ───────────────────────────────────────────────────────────────────

@router.post("/topics", response_model=TopicResponse, status_code=201)
async def create_topic(
    body: TopicCreateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.create_topic(
        subject_id=body.subject_id, name=body.name, description=body.description, db=db
    )


@router.get("/topics", response_model=list[TopicResponse])
async def list_topics(
    subject_id: str | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.list_topics(db=db, subject_id=subject_id)


@router.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.get_topic(topic_id=topic_id, db=db)


@router.patch("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    body: TopicUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.update_topic(
        topic_id=topic_id,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
        db=db,
    )


# ── SkillTags ─────────────────────────────────────────────────────────────────

@router.post("/skill-tags", response_model=SkillTagResponse, status_code=201)
async def create_skill_tag(
    body: SkillTagCreateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.create_skill_tag(
        name=body.name, subject_id=body.subject_id, db=db
    )


@router.get("/skill-tags", response_model=list[SkillTagResponse])
async def list_skill_tags(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.list_skill_tags(db=db)


@router.get("/skill-tags/{skill_tag_id}", response_model=SkillTagResponse)
async def get_skill_tag(
    skill_tag_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.get_skill_tag(skill_tag_id=skill_tag_id, db=db)


@router.patch("/skill-tags/{skill_tag_id}", response_model=SkillTagResponse)
async def update_skill_tag(
    skill_tag_id: str,
    body: SkillTagUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await content_service.update_skill_tag(
        skill_tag_id=skill_tag_id, name=body.name, is_active=body.is_active, db=db
    )
```

- [ ] **Step 4: Register the admin content router**

Edit `backend/app/api/v1/router.py` to add the admin content router:

```python
from fastapi import APIRouter

from app.api.v1 import auth, parents, students
from app.api.v1.admin import content as admin_content

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(parents.router)
router.include_router(students.router)
router.include_router(admin_content.router)
```

- [ ] **Step 5: Run tests — expect all to pass**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/test_admin_content.py -v --tb=short
```

Expected: all 16 tests pass.

- [ ] **Step 6: Run full suite to check no regressions**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/ -q --tb=short
```

Expected: all tests pass (36 existing + 16 new).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/admin/ backend/app/api/v1/router.py backend/tests/test_admin_content.py
git commit -m "feat(m2): taxonomy admin API (Subject, ExamType, Topic, SkillTag) + tests"
```

---

## Task 7: Question Schemas

**Files:**
- Create: `backend/app/schemas/question.py`

- [ ] **Step 1: Write question Pydantic schemas**

Create `backend/app/schemas/question.py`:

```python
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.question import (
    ContentOwnershipType,
    DifficultyLevel,
    PoolType,
    QuestionStatus,
    QuestionType,
    SourceType,
)


class QuestionVersionResponse(BaseModel):
    id: str
    question_id: str
    version_number: int
    stem: str
    correct_answer: str | None
    full_explanation: str
    marks: int
    options_json: list | None
    metadata_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionResponse(BaseModel):
    id: str
    subject_id: str
    exam_type_id: str
    year_level: int
    topic_id: str | None
    difficulty: DifficultyLevel
    question_type: QuestionType
    status: QuestionStatus
    source_type: SourceType
    content_ownership: ContentOwnershipType
    copyright_note: str | None
    current_version: QuestionVersionResponse | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuestionCreateRequest(BaseModel):
    subject_id: str
    exam_type_id: str
    year_level: int
    topic_id: str | None = None
    difficulty: DifficultyLevel
    question_type: QuestionType
    source_type: SourceType
    content_ownership: ContentOwnershipType
    copyright_note: str | None = None
    # First version content — always required at creation
    stem: str
    correct_answer: str | None = None
    full_explanation: str
    marks: int = 1
    options_json: list | None = None

    @field_validator("year_level")
    @classmethod
    def valid_year(cls, v: int) -> int:
        if v not in range(3, 13):
            raise ValueError("year_level must be between 3 and 12")
        return v

    @field_validator("stem")
    @classmethod
    def stem_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("stem cannot be empty")
        return v

    @field_validator("full_explanation")
    @classmethod
    def explanation_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_explanation cannot be empty")
        return v

    @field_validator("marks")
    @classmethod
    def marks_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("marks must be at least 1")
        return v


class QuestionVersionCreateRequest(BaseModel):
    stem: str
    correct_answer: str | None = None
    full_explanation: str
    marks: int = 1
    options_json: list | None = None

    @field_validator("stem")
    @classmethod
    def stem_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("stem cannot be empty")
        return v

    @field_validator("full_explanation")
    @classmethod
    def explanation_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_explanation cannot be empty")
        return v


class QuestionStatusRequest(BaseModel):
    status: QuestionStatus


class PoolCreateRequest(BaseModel):
    name: str
    description: str | None = None
    subject_id: str | None = None
    exam_type_id: str | None = None
    year_level: int | None = None

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class PoolResponse(BaseModel):
    id: str
    name: str
    description: str | None
    subject_id: str | None
    exam_type_id: str | None
    year_level: int | None
    pool_type: PoolType
    created_at: datetime

    model_config = {"from_attributes": True}


class PoolMemberAddRequest(BaseModel):
    question_id: str
```

- [ ] **Step 2: Verify import**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/python -c "from app.schemas.question import QuestionCreateRequest; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/question.py
git commit -m "feat(m2): question/version/pool Pydantic schemas"
```

---

## Task 8: Question Service

**Files:**
- Create: `backend/app/services/question_service.py`

- [ ] **Step 1: Write the question service**

Create `backend/app/services/question_service.py`:

```python
from datetime import datetime, timezone
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    SourceType,
)


# ── Publishing constraint ─────────────────────────────────────────────────────

_BLOCKED_OWNERSHIP = frozenset({
    ContentOwnershipType.internal_draft,
    ContentOwnershipType.restricted_reference_only,
})

# Valid status transitions: current → allowed next states
_VALID_TRANSITIONS: dict[QuestionStatus, frozenset[QuestionStatus]] = {
    QuestionStatus.draft: frozenset({QuestionStatus.review}),
    QuestionStatus.review: frozenset({QuestionStatus.approved, QuestionStatus.rejected}),
    QuestionStatus.rejected: frozenset({QuestionStatus.draft}),
    QuestionStatus.approved: frozenset({QuestionStatus.published, QuestionStatus.archived}),
    QuestionStatus.published: frozenset({QuestionStatus.archived}),
    QuestionStatus.archived: frozenset(),
}


# ── Question CRUD ─────────────────────────────────────────────────────────────

async def create_question(
    subject_id: str,
    exam_type_id: str,
    year_level: int,
    difficulty: DifficultyLevel,
    question_type: QuestionType,
    source_type: SourceType,
    content_ownership: ContentOwnershipType,
    stem: str,
    full_explanation: str,
    created_by_admin_id: str,
    db: AsyncSession,
    topic_id: str | None = None,
    copyright_note: str | None = None,
    correct_answer: str | None = None,
    marks: int = 1,
    options_json: list | None = None,
) -> Question:
    question = Question(
        subject_id=subject_id,
        exam_type_id=exam_type_id,
        year_level=year_level,
        topic_id=topic_id,
        difficulty=difficulty,
        question_type=question_type,
        status=QuestionStatus.draft,
        source_type=source_type,
        content_ownership=content_ownership,
        copyright_note=copyright_note,
        created_by_admin_id=created_by_admin_id,
        current_version_id=None,
    )
    db.add(question)
    await db.flush()

    version = QuestionVersion(
        question_id=question.id,
        version_number=1,
        stem=stem,
        correct_answer=correct_answer,
        full_explanation=full_explanation,
        marks=marks,
        options_json=options_json,
        created_by_admin_id=created_by_admin_id,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(version)
    await db.flush()

    question.current_version_id = version.id
    await db.commit()

    return await get_question(question.id, db)


async def get_question(question_id: str, db: AsyncSession) -> Question:
    result = await db.execute(
        select(Question)
        .options(selectinload(Question.current_version))
        .where(Question.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


async def list_questions(
    db: AsyncSession,
    status_filter: QuestionStatus | None = None,
    subject_id: str | None = None,
    exam_type_id: str | None = None,
) -> list[Question]:
    query = select(Question).options(selectinload(Question.current_version))
    if status_filter is not None:
        query = query.where(Question.status == status_filter)
    if subject_id:
        query = query.where(Question.subject_id == subject_id)
    if exam_type_id:
        query = query.where(Question.exam_type_id == exam_type_id)
    result = await db.execute(query.order_by(Question.created_at.desc()))
    return list(result.scalars().all())


async def add_version(
    question_id: str,
    stem: str,
    full_explanation: str,
    created_by_admin_id: str,
    db: AsyncSession,
    correct_answer: str | None = None,
    marks: int = 1,
    options_json: list | None = None,
) -> QuestionVersion:
    question = await get_question(question_id, db)

    result = await db.execute(
        select(func.max(QuestionVersion.version_number)).where(
            QuestionVersion.question_id == question_id
        )
    )
    max_ver = result.scalar_one_or_none() or 0

    version = QuestionVersion(
        question_id=question.id,
        version_number=max_ver + 1,
        stem=stem,
        correct_answer=correct_answer,
        full_explanation=full_explanation,
        marks=marks,
        options_json=options_json,
        created_by_admin_id=created_by_admin_id,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(version)
    await db.flush()

    question.current_version_id = version.id
    # Re-enter review when content changes (unless already archived)
    if question.status not in (QuestionStatus.draft, QuestionStatus.archived):
        question.status = QuestionStatus.review

    await db.commit()
    await db.refresh(version)
    return version


async def list_versions(question_id: str, db: AsyncSession) -> list[QuestionVersion]:
    result = await db.execute(
        select(QuestionVersion)
        .where(QuestionVersion.question_id == question_id)
        .order_by(QuestionVersion.version_number)
    )
    return list(result.scalars().all())


async def transition_status(
    question_id: str, new_status: QuestionStatus, db: AsyncSession
) -> Question:
    question = await get_question(question_id, db)

    allowed = _VALID_TRANSITIONS.get(question.status, frozenset())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot transition from '{question.status}' to '{new_status}'",
        )

    if new_status == QuestionStatus.published:
        if question.content_ownership in _BLOCKED_OWNERSHIP:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Questions with '{question.content_ownership}' ownership cannot be published. "
                    "Update the content_ownership classification first."
                ),
            )

    question.status = new_status
    await db.commit()
    await db.refresh(question)
    await db.refresh(question, attribute_names=["current_version"])
    return question


# ── Pool management ───────────────────────────────────────────────────────────

async def create_pool(
    name: str,
    created_by_admin_id: str,
    db: AsyncSession,
    description: str | None = None,
    subject_id: str | None = None,
    exam_type_id: str | None = None,
    year_level: int | None = None,
) -> QuestionPool:
    pool = QuestionPool(
        name=name,
        description=description,
        subject_id=subject_id,
        exam_type_id=exam_type_id,
        year_level=year_level,
        pool_type=PoolType.static,
        created_by_admin_id=created_by_admin_id,
    )
    db.add(pool)
    await db.commit()
    await db.refresh(pool)
    return pool


async def get_pool(pool_id: str, db: AsyncSession) -> QuestionPool:
    result = await db.execute(select(QuestionPool).where(QuestionPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")
    return pool


async def list_pools(db: AsyncSession) -> list[QuestionPool]:
    result = await db.execute(select(QuestionPool).order_by(QuestionPool.name))
    return list(result.scalars().all())


async def add_to_pool(
    pool_id: str, question_id: str, admin_id: str, db: AsyncSession
) -> None:
    await get_pool(pool_id, db)
    await get_question(question_id, db)

    existing = await db.execute(
        select(QuestionPoolMembership)
        .where(QuestionPoolMembership.pool_id == pool_id)
        .where(QuestionPoolMembership.question_id == question_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Question already in pool"
        )

    membership = QuestionPoolMembership(
        pool_id=pool_id,
        question_id=question_id,
        added_at=datetime.now(tz=timezone.utc),
        added_by_admin_id=admin_id,
    )
    db.add(membership)
    await db.commit()


async def list_pool_members(pool_id: str, db: AsyncSession) -> list[Question]:
    await get_pool(pool_id, db)
    result = await db.execute(
        select(Question)
        .join(QuestionPoolMembership, QuestionPoolMembership.question_id == Question.id)
        .where(QuestionPoolMembership.pool_id == pool_id)
        .options(selectinload(Question.current_version))
        .order_by(QuestionPoolMembership.added_at)
    )
    return list(result.scalars().all())


async def remove_from_pool(pool_id: str, question_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(QuestionPoolMembership)
        .where(QuestionPoolMembership.pool_id == pool_id)
        .where(QuestionPoolMembership.question_id == question_id)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not in pool"
        )
    await db.delete(membership)
    await db.commit()
```

- [ ] **Step 2: Verify import**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/python -c "from app.services import question_service; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/question_service.py
git commit -m "feat(m2): question service (lifecycle, versioning, pool management)"
```

---

## Task 9: Question Admin API + Tests

**Files:**
- Create: `backend/app/api/v1/admin/questions.py`
- Create: `backend/tests/test_admin_questions.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin_questions.py`:

```python
from fastapi.testclient import TestClient

from tests.conftest import auth_headers, create_admin_and_login


def _make_taxonomy(client: TestClient, tokens: dict) -> tuple[str, str]:
    """Create subject + exam_type, return (subject_id, exam_type_id)."""
    subj = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    ).json()
    et = client.post(
        "/api/v1/admin/exam-types",
        json={"code": "oc", "name": "Opportunity Class"},
        headers=auth_headers(tokens),
    ).json()
    return subj["id"], et["id"]


def _make_question_payload(subject_id: str, exam_type_id: str) -> dict:
    return {
        "subject_id": subject_id,
        "exam_type_id": exam_type_id,
        "year_level": 5,
        "difficulty": "medium",
        "question_type": "mcq",
        "source_type": "manual",
        "content_ownership": "original",
        "stem": "What is 2 + 2?",
        "correct_answer": "A",
        "full_explanation": "2 + 2 = 4, which is option A.",
        "marks": 1,
        "options_json": [
            {"label": "A", "text": "4", "is_correct": True, "explanation": "Correct"},
            {"label": "B", "text": "3", "is_correct": False, "explanation": "Too low"},
            {"label": "C", "text": "5", "is_correct": False, "explanation": "Too high"},
            {"label": "D", "text": "6", "is_correct": False, "explanation": "Too high"},
        ],
    }


def test_admin_can_create_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    resp = client.post(
        "/api/v1/admin/questions",
        json=_make_question_payload(sid, eid),
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["current_version"]["version_number"] == 1
    assert data["current_version"]["stem"] == "What is 2 + 2?"
    assert data["year_level"] == 5


def test_non_admin_cannot_create_question(client: TestClient):
    from tests.conftest import register_parent
    tokens = register_parent(client)
    resp = client.post("/api/v1/admin/questions", json={}, headers=auth_headers(tokens))
    assert resp.status_code == 403


def test_question_starts_as_draft(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    resp = client.post(
        "/api/v1/admin/questions",
        json=_make_question_payload(sid, eid),
        headers=auth_headers(tokens),
    )
    assert resp.json()["status"] == "draft"


def test_admin_can_list_questions(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens))
    client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/questions", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_can_filter_questions_by_status(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    # Advance one to review
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    # Create a second still-draft question
    client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens))
    draft_resp = client.get("/api/v1/admin/questions?status=draft", headers=auth_headers(tokens))
    assert len(draft_resp.json()) == 1
    review_resp = client.get("/api/v1/admin/questions?status=review", headers=auth_headers(tokens))
    assert len(review_resp.json()) == 1


def test_admin_can_get_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    created = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.get(f"/api/v1/admin/questions/{created['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_nonexistent_question_returns_404(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.get("/api/v1/admin/questions/nonexistent-id", headers=auth_headers(tokens))
    assert resp.status_code == 404


def test_status_transition_draft_to_review(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "review"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "review"


def test_status_transition_review_to_approved(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "approved"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_can_publish_original_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "approved"}, headers=auth_headers(tokens))
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


def test_cannot_publish_internal_draft_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    payload = _make_question_payload(sid, eid)
    payload["content_ownership"] = "internal_draft"
    q = client.post("/api/v1/admin/questions", json=payload, headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "approved"}, headers=auth_headers(tokens))
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_cannot_publish_restricted_reference_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    payload = _make_question_payload(sid, eid)
    payload["content_ownership"] = "restricted_reference_only"
    q = client.post("/api/v1/admin/questions", json=payload, headers=auth_headers(tokens)).json()
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "review"}, headers=auth_headers(tokens))
    client.patch(f"/api/v1/admin/questions/{q['id']}/status", json={"status": "approved"}, headers=auth_headers(tokens))
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_invalid_status_transition_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    # draft → published directly is invalid
    resp = client.patch(
        f"/api/v1/admin/questions/{q['id']}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


def test_admin_can_add_new_version(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.post(
        f"/api/v1/admin/questions/{q['id']}/versions",
        json={
            "stem": "What is 3 + 3?",
            "correct_answer": "B",
            "full_explanation": "3 + 3 = 6, which is option B.",
            "marks": 1,
            "options_json": [
                {"label": "A", "text": "5", "is_correct": False, "explanation": "Wrong"},
                {"label": "B", "text": "6", "is_correct": True, "explanation": "Correct"},
            ],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["version_number"] == 2
    assert resp.json()["stem"] == "What is 3 + 3?"


def test_new_version_updates_current_version_on_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    assert q["current_version"]["version_number"] == 1
    client.post(
        f"/api/v1/admin/questions/{q['id']}/versions",
        json={"stem": "Updated stem.", "full_explanation": "Updated explanation.", "marks": 1},
        headers=auth_headers(tokens),
    )
    updated = client.get(f"/api/v1/admin/questions/{q['id']}", headers=auth_headers(tokens)).json()
    assert updated["current_version"]["version_number"] == 2


def test_admin_can_list_versions(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.post(
        f"/api/v1/admin/questions/{q['id']}/versions",
        json={"stem": "V2 stem.", "full_explanation": "V2 explanation.", "marks": 1},
        headers=auth_headers(tokens),
    )
    resp = client.get(f"/api/v1/admin/questions/{q['id']}/versions", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.json()[0]["version_number"] == 1
    assert resp.json()[1]["version_number"] == 2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/test_admin_questions.py -q --tb=line 2>&1 | head -20
```

Expected: failures (routes not yet registered).

- [ ] **Step 3: Write question admin router**

Create `backend/app/api/v1/admin/questions.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.question import QuestionStatus
from app.models.user import AdminProfile, User
from app.schemas.question import (
    QuestionCreateRequest,
    QuestionResponse,
    QuestionStatusRequest,
    QuestionVersionCreateRequest,
    QuestionVersionResponse,
)
from app.services import question_service

router = APIRouter(prefix="/admin", tags=["admin-questions"])


@router.post("/questions", response_model=QuestionResponse, status_code=201)
async def create_question(
    body: QuestionCreateRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.create_question(
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
        year_level=body.year_level,
        difficulty=body.difficulty,
        question_type=body.question_type,
        source_type=body.source_type,
        content_ownership=body.content_ownership,
        stem=body.stem,
        full_explanation=body.full_explanation,
        created_by_admin_id=admin_profile.id,
        db=db,
        topic_id=body.topic_id,
        copyright_note=body.copyright_note,
        correct_answer=body.correct_answer,
        marks=body.marks,
        options_json=body.options_json,
    )


@router.get("/questions", response_model=list[QuestionResponse])
async def list_questions(
    status: QuestionStatus | None = None,
    subject_id: str | None = None,
    exam_type_id: str | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_questions(
        db=db,
        status_filter=status,
        subject_id=subject_id,
        exam_type_id=exam_type_id,
    )


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.get_question(question_id=question_id, db=db)


@router.patch("/questions/{question_id}/status", response_model=QuestionResponse)
async def update_question_status(
    question_id: str,
    body: QuestionStatusRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.transition_status(
        question_id=question_id, new_status=body.status, db=db
    )


@router.post(
    "/questions/{question_id}/versions",
    response_model=QuestionVersionResponse,
    status_code=201,
)
async def add_question_version(
    question_id: str,
    body: QuestionVersionCreateRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.add_version(
        question_id=question_id,
        stem=body.stem,
        full_explanation=body.full_explanation,
        created_by_admin_id=admin_profile.id,
        db=db,
        correct_answer=body.correct_answer,
        marks=body.marks,
        options_json=body.options_json,
    )


@router.get(
    "/questions/{question_id}/versions",
    response_model=list[QuestionVersionResponse],
)
async def list_question_versions(
    question_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_versions(question_id=question_id, db=db)
```

- [ ] **Step 4: Register question router**

Edit `backend/app/api/v1/router.py`:

```python
from fastapi import APIRouter

from app.api.v1 import auth, parents, students
from app.api.v1.admin import content as admin_content
from app.api.v1.admin import questions as admin_questions

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(parents.router)
router.include_router(students.router)
router.include_router(admin_content.router)
router.include_router(admin_questions.router)
```

- [ ] **Step 5: Run question tests — expect all to pass**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/test_admin_questions.py -v --tb=short
```

Expected: all 17 tests pass.

- [ ] **Step 6: Run full suite**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/ -q --tb=short
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/admin/questions.py backend/app/api/v1/router.py backend/tests/test_admin_questions.py
git commit -m "feat(m2): question admin API (create, list, get, version, status) + tests"
```

---

## Task 10: Question Pool Admin API + Tests

**Files:**
- Create: `backend/app/api/v1/admin/pools.py`
- Create: `backend/tests/test_admin_pools.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin_pools.py`:

```python
from fastapi.testclient import TestClient

from tests.conftest import auth_headers, create_admin_and_login


def _make_taxonomy(client: TestClient, tokens: dict) -> tuple[str, str]:
    subj = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    ).json()
    et = client.post(
        "/api/v1/admin/exam-types",
        json={"code": "oc", "name": "Opportunity Class"},
        headers=auth_headers(tokens),
    ).json()
    return subj["id"], et["id"]


def _make_question_payload(subject_id: str, exam_type_id: str) -> dict:
    return {
        "subject_id": subject_id,
        "exam_type_id": exam_type_id,
        "year_level": 5,
        "difficulty": "medium",
        "question_type": "mcq",
        "source_type": "manual",
        "content_ownership": "original",
        "stem": "What is 2 + 2?",
        "correct_answer": "A",
        "full_explanation": "2 + 2 = 4.",
        "marks": 1,
    }


def test_admin_can_create_pool(client: TestClient):
    tokens = create_admin_and_login(client)
    resp = client.post(
        "/api/v1/admin/pools",
        json={"name": "Year 5 OC Maths"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Year 5 OC Maths"
    assert data["pool_type"] == "static"


def test_non_admin_cannot_create_pool(client: TestClient):
    from tests.conftest import register_parent
    tokens = register_parent(client)
    resp = client.post("/api/v1/admin/pools", json={"name": "Pool"}, headers=auth_headers(tokens))
    assert resp.status_code == 403


def test_admin_can_list_pools(client: TestClient):
    tokens = create_admin_and_login(client)
    client.post("/api/v1/admin/pools", json={"name": "Pool A"}, headers=auth_headers(tokens))
    client.post("/api/v1/admin/pools", json={"name": "Pool B"}, headers=auth_headers(tokens))
    resp = client.get("/api/v1/admin/pools", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_admin_can_get_pool(client: TestClient):
    tokens = create_admin_and_login(client)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool A"}, headers=auth_headers(tokens)).json()
    resp = client.get(f"/api/v1/admin/pools/{pool['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["id"] == pool["id"]


def test_admin_can_add_question_to_pool(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.post(
        f"/api/v1/admin/pools/{pool['id']}/members",
        json={"question_id": q["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201


def test_admin_can_list_pool_members(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.post(f"/api/v1/admin/pools/{pool['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    resp = client.get(f"/api/v1/admin/pools/{pool['id']}/members", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == q["id"]


def test_duplicate_pool_membership_rejected(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.post(f"/api/v1/admin/pools/{pool['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    resp = client.post(
        f"/api/v1/admin/pools/{pool['id']}/members",
        json={"question_id": q["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_admin_can_remove_question_from_pool(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    client.post(f"/api/v1/admin/pools/{pool['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    resp = client.delete(
        f"/api/v1/admin/pools/{pool['id']}/members/{q['id']}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 204
    members = client.get(f"/api/v1/admin/pools/{pool['id']}/members", headers=auth_headers(tokens)).json()
    assert len(members) == 0


def test_remove_nonexistent_member_returns_404(client: TestClient):
    tokens = create_admin_and_login(client)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    resp = client.delete(
        f"/api/v1/admin/pools/{pool['id']}/members/nonexistent-id",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


def test_add_to_nonexistent_pool_returns_404(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    resp = client.post(
        "/api/v1/admin/pools/nonexistent-pool/members",
        json={"question_id": q["id"]},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


def test_add_nonexistent_question_to_pool_returns_404(client: TestClient):
    tokens = create_admin_and_login(client)
    pool = client.post("/api/v1/admin/pools", json={"name": "Pool 1"}, headers=auth_headers(tokens)).json()
    resp = client.post(
        f"/api/v1/admin/pools/{pool['id']}/members",
        json={"question_id": "nonexistent-question"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 404


def test_question_can_be_in_multiple_pools(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    pool_a = client.post("/api/v1/admin/pools", json={"name": "Pool A"}, headers=auth_headers(tokens)).json()
    pool_b = client.post("/api/v1/admin/pools", json={"name": "Pool B"}, headers=auth_headers(tokens)).json()
    q = client.post("/api/v1/admin/questions", json=_make_question_payload(sid, eid), headers=auth_headers(tokens)).json()
    r1 = client.post(f"/api/v1/admin/pools/{pool_a['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    r2 = client.post(f"/api/v1/admin/pools/{pool_b['id']}/members", json={"question_id": q["id"]}, headers=auth_headers(tokens))
    assert r1.status_code == 201
    assert r2.status_code == 201
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/test_admin_pools.py -q --tb=line 2>&1 | head -20
```

Expected: failures (routes not yet registered).

- [ ] **Step 3: Write pool admin router**

Create `backend/app/api/v1/admin/pools.py`:

```python
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.user import AdminProfile, User
from app.schemas.question import (
    PoolCreateRequest,
    PoolMemberAddRequest,
    PoolResponse,
    QuestionResponse,
)
from app.services import question_service

router = APIRouter(prefix="/admin", tags=["admin-pools"])


@router.post("/pools", response_model=PoolResponse, status_code=201)
async def create_pool(
    body: PoolCreateRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.create_pool(
        name=body.name,
        created_by_admin_id=admin_profile.id,
        db=db,
        description=body.description,
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
        year_level=body.year_level,
    )


@router.get("/pools", response_model=list[PoolResponse])
async def list_pools(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_pools(db=db)


@router.get("/pools/{pool_id}", response_model=PoolResponse)
async def get_pool(
    pool_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.get_pool(pool_id=pool_id, db=db)


@router.post("/pools/{pool_id}/members", status_code=201)
async def add_pool_member(
    pool_id: str,
    body: PoolMemberAddRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    await question_service.add_to_pool(
        pool_id=pool_id,
        question_id=body.question_id,
        admin_id=admin_profile.id,
        db=db,
    )
    return {"pool_id": pool_id, "question_id": body.question_id}


@router.get("/pools/{pool_id}/members", response_model=list[QuestionResponse])
async def list_pool_members(
    pool_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_pool_members(pool_id=pool_id, db=db)


@router.delete("/pools/{pool_id}/members/{question_id}", status_code=204)
async def remove_pool_member(
    pool_id: str,
    question_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await question_service.remove_from_pool(
        pool_id=pool_id, question_id=question_id, db=db
    )
```

- [ ] **Step 4: Register pool router**

Edit `backend/app/api/v1/router.py`:

```python
from fastapi import APIRouter

from app.api.v1 import auth, parents, students
from app.api.v1.admin import content as admin_content
from app.api.v1.admin import pools as admin_pools
from app.api.v1.admin import questions as admin_questions

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(parents.router)
router.include_router(students.router)
router.include_router(admin_content.router)
router.include_router(admin_questions.router)
router.include_router(admin_pools.router)
```

- [ ] **Step 5: Run pool tests — expect all to pass**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/test_admin_pools.py -v --tb=short
```

Expected: all 11 tests pass.

- [ ] **Step 6: Run the full suite**

```bash
cd /home/pi/HSC-ai/backend && .venv/bin/pytest tests/ -q --tb=short
```

Expected: all tests pass. Count should be 36 (existing) + 16 (taxonomy) + 17 (questions) + 11 (pools) = 80 total.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/admin/pools.py backend/app/api/v1/router.py backend/tests/test_admin_pools.py
git commit -m "feat(m2): question pool admin API (create, list, members) + tests"
```

---

## Self-Review Checklist

**Spec coverage:**

| Requirement | Task |
|-------------|------|
| Subjects and exam types | Tasks 1, 5, 6 |
| Topics and skill tags | Tasks 1, 5, 6 |
| Questions with version history | Tasks 2, 8, 9 |
| Question options and explanations | Tasks 2, 7, 8 (options_json field) |
| Content ownership classification + publish block | Tasks 2, 8 (_BLOCKED_OWNERSHIP in transition_status) |
| Writing prompts (question_type=extended_response) | Tasks 2, 7 (extended_response in QuestionType enum) |
| Admin CRUD for all content types | Tasks 6, 9, 10 |
| Content lifecycle: draft→review→approved→published→archived | Task 8 (_VALID_TRANSITIONS dict) |

All Phase 3 requirements are covered. Phase 4 (Exam Engine) is explicitly deferred.

**Placeholder scan:** No TBDs, TODOs, or "similar to" references. All code steps contain complete, runnable code.

**Type consistency:** `QuestionVersionResponse` is defined in Task 7 schemas and used in Task 9 API. `QuestionResponse` includes `current_version: QuestionVersionResponse | None`. `PoolResponse` uses `PoolType` from the model. All consistent.
