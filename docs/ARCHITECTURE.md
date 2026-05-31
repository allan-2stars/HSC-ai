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

- Cloudflare R2 or S3-compatible object storage

Future services:

- Redis for queues, caching, or rate limiting
- Background worker for OCR and AI extraction

## 2. High-Level Architecture

```text
Browser / PWA / iPad
        |
        v
Next.js Frontend
        |
        v
FastAPI Backend
        |
        +--> PostgreSQL
        +--> Object Storage
        +--> OCR Worker
        +--> AI Provider Router
```

## 3. Main Modules

### Auth and Accounts

Handles:

- Parent login
- Student login
- Admin login
- Role-based access
- Parent-student linking

### Subscription and Entitlement

Handles:

- Product packages
- Billing period
- Feature access
- Subject/exam type access
- Premium AI access

### Exam Engine

Handles:

- Exam sessions
- Timers
- Submission
- Auto-marking
- Attempt history
- Integrity events

### Question Bank

Handles:

- Questions
- Options
- Explanations
- Topic tags
- Difficulty
- Versioning
- Content status

### OCR Import

Handles:

- Source file upload
- PDF/image processing
- OCR text extraction
- AI structure extraction
- Review queue

### AI Provider Layer

Handles:

- Provider routing
- Prompt execution
- JSON schema extraction
- Explanation generation
- Question generation
- Weakness analysis

### Analytics

Handles:

- Attempt scoring
- Topic-level weakness summary
- Parent reports
- Recommendations

## 4. Service Boundaries

Business logic should live in service modules, not route handlers.

Examples:

- `ExamAttemptService`
- `QuestionBankService`
- `SubscriptionEntitlementService`
- `OCRImportService`
- `AIProviderService`
- `RecommendationService`

## 5. Data Principles

- Attempt submissions are immutable.
- Content has lifecycle status.
- Questions have version history.
- Source provenance is preserved.
- Admin review is mandatory before publishing generated/imported content.

## 6. API Principles

- Role-aware endpoints.
- Explicit entitlement checks.
- Additive API changes preferred.
- Separate admin APIs from student/parent APIs.

## 7. Background Processing

OCR and AI extraction should not block request/response.

Initial MVP can use database status polling. Later versions should use worker queue.

Job states:

- queued
- processing
- needs_review
- failed
- completed

## 8. Deployment Assumption

Initial development should support Docker Compose.

Production should support cloud deployment with:

- Managed PostgreSQL
- Object storage
- HTTPS
- Background workers
- Environment-based provider configuration
