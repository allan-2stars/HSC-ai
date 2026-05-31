# CODEX.md

## Purpose

This file guides Codex when generating or modifying code for the HSC Exam Platform.

## Product Summary

Build a web-first NSW exam preparation platform for OC and Selective School preparation. The platform must support students taking timed practice exams, parents managing subscriptions and student progress, and administrators managing the question bank.

## Important Constraints

- Do not start with all Year 1-12 content. V1 is OC and Selective only.
- Keep architecture extensible for NAPLAN and HSC.
- Do not couple business logic directly to DeepSeek, OpenAI, Claude, Gemini, Ollama, OpenRouter, or CC Switch.
- Use an AI provider adapter/router.
- Do not auto-publish OCR or AI-generated questions.
- Student attempts must be immutable after submission.
- Students cannot delete history.
- Parents can manage/delete/archive history according to policy.
- Every published question requires a correct answer and full explanation.

## Preferred Stack

Frontend:
- Next.js
- TypeScript
- Tailwind CSS

Backend:
- FastAPI
- Python
- PostgreSQL

Infrastructure:
- Docker Compose for local development
- S3-compatible object storage for uploads
- Redis only when queue/debounce is needed

## Coding Style

- Code and comments in English.
- Keep files modular.
- Prefer services over route-heavy business logic.
- Prefer additive changes to breaking API changes.
- Add tests for all business logic.

## Milestone Hygiene

Do not combine unrelated work. A milestone should have:

- Goal
- Changed files
- Tests
- Verification command
- Known risks/deferred items

## Core Domain Entities

- Account/User
- ParentProfile
- StudentProfile
- AdminProfile
- Subscription
- Entitlement
- Subject
- ExamType
- Exam
- ExamSection
- Question
- QuestionOption
- QuestionVersion
- Attempt
- AttemptAnswer
- Topic
- SkillTag
- SourceFile
- OCRJob
- ContentReviewItem
- AIProviderConfig

See `docs/DATA_MODEL.md` for details.
