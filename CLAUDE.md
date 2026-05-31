# CLAUDE.md

## Project Context

This project is a NSW-focused exam preparation web platform inspired by products like IXL, but positioned around OC and Selective School preparation first, then NAPLAN and HSC later.

The project is currently in specification stage. Do not invent product behavior beyond the documents unless explicitly asked.

## Core Product Decisions

- V1 launch scope: OC and Selective School preparation.
- V2: NAPLAN.
- V3: HSC.
- Users: Parent, Student, Administrator.
- Parent account owns subscription and student data.
- One parent account can manage a maximum of 3 student accounts.
- Subscriptions support All Access, Subject packages, Exam Type packages, monthly billing, and annual billing.
- AI features are Premium-only except limited trials.
- Primary student devices: desktop, laptop, iPad, Android tablet.
- Mobile phones are acceptable for account/report viewing but not recommended for full exam mode.

## Engineering Rules

- Use English for all code, comments, commits, variable names, and documentation inside code files.
- Prefer clear, typed interfaces.
- Avoid hard-coding AI provider logic into business services.
- Keep exam attempt records immutable after submission.
- Do not allow students to delete attempt history.
- Do not auto-publish OCR or AI-generated content.
- All generated/imported content must enter admin review first.
- Browser exam-security controls are deterrence, not absolute anti-cheating.

## Recommended Stack

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, Python
- Database: PostgreSQL
- Cache/queue later: Redis
- Storage: Cloudflare R2 or S3-compatible storage
- OCR: PyMuPDF + PaddleOCR/Tesseract initially
- AI: provider abstraction with DeepSeek for development/testing, production provider configurable

## Required Reading Before Coding

Read these documents before making architectural changes:

1. `docs/PRD.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DATA_MODEL.md`
4. `docs/EXAM_ENGINE.md`
5. `docs/OCR_IMPORT_PIPELINE.md`
6. `docs/AI_PROVIDER_STRATEGY.md`
7. `docs/SECURITY_PRIVACY.md`

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
