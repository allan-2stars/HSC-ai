# Roadmap

## Phase 0: Specification

Status: complete.

Deliverables:

- Product requirements ✓
- Architecture documents ✓
- Data model ✓
- Exam engine design ✓
- OCR pipeline design ✓
- AI provider strategy ✓
- Security/privacy model ✓
- Admin content workflow ✓
- AI skill system ✓
- Architecture review ✓
- Decisions 1–7 resolved ✓

## Phase 1: Project Skeleton

Goals:

- Monorepo structure
- Docker Compose development environment (ARM64, all services)
- FastAPI backend shell
- Next.js frontend shell
- PostgreSQL connection and initial migrations
- JWT auth model (parent and admin only)
- Test framework (pytest for backend, vitest for frontend)
- MinIO and Redis connected

## Phase 2: Accounts and Subscription Foundation

Goals:

- Parent registration and login
- Student account creation by parent (family account model)
- Student first-login password setup
- Admin login
- Maximum 3 students per parent (API + DB constraint)
- Subscription and entitlement data model
- Basic plan and entitlement checks
- Role-based access control middleware

## Phase 3: Question Bank Foundation

Goals:

- Subjects and exam types
- Topics and skill tags
- Questions with version history
- Question options and explanations
- Content ownership classification field and publishing block enforcement
- Writing prompts (for Selective writing)
- Admin CRUD for all content types
- Content lifecycle: draft → review → approved → published → archived

## Phase 4: Exam Engine MVP

Goals:

- Exam builder (fixed exams)
- Timed MCQ exam mode
- Writing mode (Selective writing component)
- Attempt creation and answer capture
- Writing response capture
- Auto-submit on timeout
- Auto-marking (MCQ)
- Immutable attempt records (DB trigger)
- Immutable writing responses
- Student review after submission
- AI writing feedback (async, with mandatory disclaimer)
- Integrity event logging

## Phase 5: Parent Dashboard

Goals:

- Student selector
- Recent attempts
- Topic weaknesses (rule-based)
- Assigned exams
- Basic progress charts
- Writing attempt history

## Phase 6: OCR Import Pipeline

Goals:

- Admin file upload
- OCR job model
- OCR text extraction (PaddleOCR + Pix2Text for maths)
- AI structure extraction
- Review queue with ownership classification requirement
- Publish approved questions
- Copyright warning UI in admin review screen

## Phase 7: AI Provider Layer

Goals:

- Provider abstraction with skill system
- OpenAI provider implementation
- Ollama provider implementation (local/offline)
- Configurable provider routing via environment variable
- Admin AI question generation (OC and Selective skills)
- AI quality review assistant
- AI usage logging

## Phase 8: Premium AI Features

Goals:

- Weakness analysis
- Practice recommendations
- AI tutor explanation
- Trial usage limits

## Phase 9: PWA and Tablet Optimization

Goals:

- PWA installability
- iPad/tablet UX polish
- Exam mode screen constraints
- Writing mode on tablet

## Phase 10: NAPLAN Expansion

Goals:

- NAPLAN exam type
- Content model extensions if needed
- Additional question formats

## Phase 11: HSC Expansion

Goals:

- HSC subject support
- More complex marking
- Long-answer workflow
- Essay/rubric support
