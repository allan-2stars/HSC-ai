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

Status: complete.

Deliverables:

- Parent registration and login ✓
- Student account creation by parent (family account model) ✓
- Student first-login password setup ✓
- Admin login ✓
- Maximum 3 students per parent (API + service layer) ✓
- Subscription and entitlement data model ✓
- Basic plan seed (all_access_monthly, all_access_annual, oc_monthly, selective_monthly) ✓
- Role-based access control middleware ✓
- Audit logging (registration, login, student creation/deactivation) ✓

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

Status: **M3A (MCQ Engine) complete.** M3B (Writing, AI feedback) deferred.

M3A deliverables:

- Exam builder (fixed exams) ✓
- Timed MCQ exam mode ✓
- Attempt creation and answer capture ✓
- Auto-submit on timeout ✓
- Auto-marking (MCQ) ✓
- Immutable attempt records (service-layer checks) ✓
- Student review after submission ✓
- Audit logging (exam lifecycle events) ✓
- Version freezing at ExamInstance publish time ✓
- Admin exam template/instance management APIs ✓
- Student attempt history ✓

M3B (deferred):

- Writing mode (Selective writing component)
- Writing response capture
- Immutable writing responses
- AI writing feedback (async, with mandatory disclaimer)
- Integrity event logging

## Phase 5: Parent Dashboard & Progress Analytics

Status: **M4 complete.**

M4 deliverables:

- TopicPerformance and SkillPerformance models ✓
- On-demand analytics calculation (no background jobs needed) ✓
- Student summary: total attempts, average/best/latest score, accuracy ✓
- Topic-level performance aggregation from attempt data ✓
- Skill-level performance aggregation via question→skill_tag mappings ✓
- Rule-based weakness/strength detection (accuracy < 60% → weakness, > 85% → strength) ✓
- Rule-based recommendation text generation ✓
- Parent-only analytics APIs (summary, topics, skills, recommendations) ✓
- Parent ownership enforcement (cannot view other parents' students) ✓
- Student self-view: own progress, strengths, weaknesses ✓
- Exam history endpoint with pagination ✓
- Parent dashboard UI: student cards → detail page with stats/tables ✓
- Student progress UI: summary, recent exams, strengths/weaknesses ✓
- 12 backend tests, 3 frontend tests ✓

M4.5 deliverables (Exam Integrity & Trend Analytics):

- AttemptIntegrityEvent model (tab_hidden, tab_visible, fullscreen_enter/ex, copy/paste) ✓
- POST /attempts/{id}/integrity-event endpoint ✓
- Integrity summary aggregation on attempt submission ✓
- time_spent_seconds on AttemptAnswer (persisted, accumulates across saves) ✓
- Backend trend endpoints: parent + student, oldest→newest, limit support ✓
- Enhanced recommendations: slow_topics, average_time_seconds, time-based recs ✓
- Frontend integrity detection (visibilitychange, fullscreenchange, copy/paste) ✓
- Frontend time tracking per question ✓
- TrendChart component (SVG line chart, zero dependencies) ✓
- Slow topics display on parent + student dashboards ✓
- 13 backend tests, frontend integrity/time/tracking in page ✓

M4.6 deliverables (Parent Assignment System):

- AssignedExam model (student_id, exam_instance_id, assigned_by_parent_id, title_snapshot, due_at, status) ✓
- Assignment status lifecycle: assigned → started → completed | overdue | cancelled ✓
- assigned_exam_id on Attempt — links attempt back to assignment ✓
- Parent APIs: create, list (per-student and all), update/cancel, summary ✓
- Student APIs: list own, detail, due date display ✓
- Expired completion check on-demand (no scheduler) ✓
- Parent dashboard assignment page with status badges and cancel ✓
- Student assignment page with Start Exam / Continue buttons ✓
- Assignment-aware start: query param assignment_id links attempt ✓
- Audit logging: created, updated, cancelled, started, completed ✓
- 14 backend tests, 5 frontend tests ✓

Goals:

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
