# CLAUDE.md

## Project Context

This project is a NSW-focused exam preparation web platform inspired by products like IXL, but positioned around OC and Selective School preparation first, then NAPLAN and HSC later.

The project is currently completing specification. Implementation begins at Milestone 1.

Do not invent product behavior beyond the documents unless explicitly asked.

## Core Product Decisions

- V1 launch scope: OC and Selective School preparation (including Selective writing component).
- V2: NAPLAN.
- V3: HSC.
- Users: Parent, Student, Administrator.
- Parent account owns subscription and student data.
- Students are subordinate accounts; they cannot self-register.
- One parent account can manage a maximum of 3 student accounts.
- Students must complete password setup on first login.
- Subscriptions support All Access, Subject packages, Exam Type packages, monthly billing, and annual billing.
- AI features are Premium-only except limited trials.
- Primary student devices: desktop, laptop, iPad, Android tablet.
- Mobile phones are acceptable for account/report viewing but not recommended for full exam mode.

## Engineering Rules

- Use English for all code, comments, commits, variable names, and documentation inside code files.
- Prefer clear, typed interfaces.
- Avoid hard-coding AI provider logic into business services; use the skill abstraction layer.
- Keep exam attempt records immutable after submission (DB trigger enforced).
- Writing responses are immutable after submission.
- Do not allow students to delete attempt history.
- Do not auto-publish OCR or AI-generated content. Admin review is mandatory.
- All generated/imported content must enter admin review first.
- OCR-imported content defaults to `internal_draft` ownership; admin must assign a publishable classification.
- Questions with `internal_draft` or `restricted_reference_only` ownership cannot be published.
- Browser exam-security controls are deterrence, not absolute anti-cheating.
- Writing feedback must always display the disclaimer: "Writing feedback is educational guidance and does not represent official Selective School marking."
- Do not send student personal information (name, DOB, contact details) to external AI providers.

## Recommended Stack

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, Python
- ORM: SQLAlchemy
- Authentication: JWT (RS256) + refresh tokens (PostgreSQL-backed)
- Database: PostgreSQL
- Cache/queue: Redis (ARQ for background jobs)
- Storage: MinIO (self-hosted, S3-compatible)
- OCR: PyMuPDF + PaddleOCR; Pix2Text for maths-heavy content
- AI: provider abstraction with skill system; OpenAI or Ollama for development; production provider configurable

## Deployment Target

- Raspberry Pi 5 (ARM64)
- Docker Compose (mandatory)
- All images must support ARM64
- Cloudflare Tunnel for external access
- No Kubernetes, no managed cloud services as primary dependencies

## Required Reading Before Coding

Read these documents before making architectural changes:

1. `docs/PRD.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DATA_MODEL.md`
4. `docs/QUESTION_BANK.md`
5. `docs/EXAM_ENGINE.md`
6. `docs/CONTENT_STRATEGY.md`
7. `docs/OCR_IMPORT_PIPELINE.md`
8. `docs/AI_PROVIDER_STRATEGY.md`
9. `docs/SECURITY_PRIVACY.md`
10. `docs/ADMIN_CONTENT_WORKFLOW.md`
11. `docs/OPEN_DECISIONS.md`

Also review applicable skills in `skills/` before implementing AI or exam content features.

## Implementation Discipline

When asked to implement, keep changes milestone-scoped. Do not implement future phases unless explicitly requested.

For each coding task:

1. Restate the milestone goal briefly.
2. Inspect relevant files first.
3. Make minimal cohesive changes.
4. Add or update tests.
5. Run the relevant test commands.
6. Report changed files and verification results.

## Non-Goals for V1

- School/teacher portal.
- HSC long-answer marking.
- Native mobile apps.
- Fully automated OCR publishing.
- Full anti-cheating enforcement.
- Complex AI adaptive learning from day one.
- AI-powered writing marks or grades (feedback only).
- Automatic copyright determination for OCR content.
