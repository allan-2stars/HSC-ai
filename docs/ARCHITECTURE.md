# Architecture Specification

## 1. Recommended Stack

Frontend:

- Next.js
- TypeScript
- Tailwind CSS

Backend:

- FastAPI
- Python

Database:

- PostgreSQL

Storage:

- MinIO (self-hosted, S3-compatible) — primary storage for development and production on Raspberry Pi
- S3-compatible cloud storage — optional alternative for cloud deployments

Cache and Queue:

- Redis — session management, background job queues, rate limiting

Background Workers:

- ARQ (Async Redis Queue) — lightweight background job processing for OCR and AI tasks
- Separate worker containers in Docker Compose

## 2. Deployment Target

Primary target: Raspberry Pi 5 running Docker Compose, exposed via Cloudflare Tunnel.

Requirements:

- All services must run as Docker containers.
- All images must support ARM64 architecture.
- No Kubernetes, no managed cloud services as primary dependencies.
- Local development and production must use the same Docker Compose architecture.

Docker Compose services:

- `postgres` — PostgreSQL 16 (ARM64 compatible)
- `redis` — Redis 7 (ARM64 compatible)
- `minio` — MinIO object storage (ARM64 compatible)
- `backend` — FastAPI application
- `frontend` — Next.js application
- `ocr-worker` — OCR background worker (heavy; started via Docker Compose profile)
- `ai-worker` — AI background worker (started via Docker Compose profile)
- `nginx` — reverse proxy

## 3. High-Level Architecture

```text
Browser / PWA / iPad
        |
        v
Cloudflare Tunnel
        |
        v
Nginx (reverse proxy)
        |
        +---> Next.js Frontend (:3000)
        +---> FastAPI Backend (:8000)
                |
                +--> PostgreSQL
                +--> Redis
                +--> MinIO
                +--> OCR Worker (via ARQ queue)
                +--> AI Worker (via ARQ queue)
                +--> AI Provider Router (external APIs)
```

## 4. Main Modules

### Auth and Accounts

Handles:

- Parent registration and login
- Student first-login password setup
- Admin login
- Family account model (parent owns student accounts)
- Role-based access control
- JWT (RS256) access tokens with PostgreSQL-backed refresh tokens
- Student session scoped to limited capabilities (no billing access)

Family account rules enforced here:

- Maximum 3 student accounts per parent (API + DB constraint)
- Student cannot self-register
- Parent can reset student credentials

### Subscription and Entitlement

Handles:

- Product packages (All Access, Subject, Exam Type)
- Billing period (monthly, annual)
- Feature access gating
- Premium AI access control
- Entitlement checks before exam start and AI feature use

### Exam Engine

Handles:

- Standard exam sessions (MCQ, structured answers)
- Writing exam sessions (Selective writing component)
- Timed exam flow with server-authoritative start time
- Submission and auto-marking
- Immutable attempt records (DB trigger enforced)
- Writing response storage
- AI writing feedback generation (async, via AI worker)
- Integrity event logging

### Question Bank

Handles:

- Questions with version history
- MCQ options and explanations
- Writing prompts
- Topic and skill tags
- Difficulty classification
- Content ownership classification (required on all questions)
- Content status lifecycle (draft → review → approved → published → archived)
- Publishing blocked for `internal_draft` and `restricted_reference_only` content

### OCR Import

Handles:

- Source file upload and storage
- PDF native text extraction
- OCR processing (PaddleOCR, with Pix2Text for maths)
- AI structure extraction
- Review queue with ownership classification requirement
- Traceability metadata

### AI Provider Layer

Handles:

- Provider abstraction interface
- Skill-based routing (NSW OC generation, Selective generation, writing assessment, quality review)
- Privacy-safe payload construction (no PII in AI requests)
- Category A (admin-only) vs. Category B (student-facing) routing
- Writing assessment with disclaimer enforcement
- AI usage logging

Approved providers:

- OpenAI
- Anthropic (Claude)
- Ollama (local/offline)
- OpenRouter (admin-only, with documented provider chain)

Not approved:

- DeepSeek (PRC data localisation risk — see AI_PROVIDER_STRATEGY.md)

### Analytics

Handles:

- Attempt scoring and history
- Topic-level weakness summary (rule-based in V1)
- Parent progress reports
- Score trends
- Time analysis

V1 analytics are rule-based SQL queries. AI-powered recommendations deferred to V2+.

## 5. AI Skill System

The AI provider layer uses a skill system to define AI responsibilities. Skills are documented in the `skills/` directory.

Implemented skills:

- `nsw-oc-question-generation` — generates OC exam question drafts
- `nsw-selective-question-generation` — generates Selective exam question drafts including writing prompts
- `writing-assessment` — provides writing feedback for Selective responses
- `question-quality-review` — reviews generated/imported questions before admin approval

Business services must call AI through skills. Direct provider API calls from route handlers are not permitted.

## 6. Service Boundaries

Business logic must live in service modules, not route handlers.

Examples:

- `ExamAttemptService`
- `QuestionBankService`
- `SubscriptionEntitlementService`
- `OCRImportService`
- `AIProviderService`
- `WritingAssessmentService`
- `RecommendationService`

## 7. Data Principles

- Attempt submissions are immutable (DB trigger enforced).
- Writing responses are immutable after submission.
- Content has lifecycle status with ownership classification gate on publishing.
- Questions have version history; attempt answers reference the version active at attempt time.
- Source provenance is preserved on all imported content.
- Admin review is mandatory before publishing generated or imported content.
- AI-generated content can never be auto-published.

## 8. API Principles

- Role-aware endpoints with explicit entitlement checks.
- Separate admin APIs from student/parent APIs.
- Additive API changes preferred.
- Versioned under `/api/v1/`.

## 9. Background Processing

OCR and AI extraction must not block the request/response cycle.

Background jobs use ARQ with Redis as the broker.

Job states:

- `queued`
- `processing`
- `needs_review`
- `failed`
- `completed`

OCR worker and AI worker run as separate Docker containers using the `profiles` feature in Docker Compose to manage resource usage on constrained hardware.

## 10. Future Extensions

### School and Organisation Support

School or tutoring centre accounts are not part of V1.

The data model reserves a nullable `organization_id` field on `ParentProfile` to support future linkage without a breaking schema migration.

When implemented, the hierarchy would be:

```text
Organization (school / tutoring centre)
  └── Staff Account
       └── Class or Group
            └── Students
```

No implementation is required in V1. The nullable FK column costs nothing and prevents a painful future migration.

See `DATA_MODEL.md` section 9 for the proposed future schema.
