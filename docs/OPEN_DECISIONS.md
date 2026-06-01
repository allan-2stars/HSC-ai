# Open Decisions

Decisions marked **[RESOLVED]** have been finalised and reflected in the relevant documentation. Do not reopen resolved decisions without a documented justification.

---

## Resolved Decisions

### [RESOLVED] Student Authentication Model

Decision: Family Account model adopted.

- Parent creates student accounts. Students do not self-register.
- First login requires student to set their own password.
- Parent can reset student passwords.
- Student accounts cannot access billing or subscription settings.
- Maximum 3 student accounts per parent in V1.
- Student accounts are subordinate and cannot exist without a linked parent.

Documented in: DATA_MODEL.md, SECURITY_PRIVACY.md, PRD.md, ARCHITECTURE.md

---

### [RESOLVED] Copyright and OCR Content Policy

Decision: OCR is an ingestion tool only. Publishing OCR-derived content requires ownership review.

Content ownership classifications introduced:

- `original` — publishing allowed
- `licensed` — publishing allowed
- `public_domain` — publishing allowed
- `approved_internal` — publishing allowed
- `user_provided_with_rights` — publishing allowed with caution
- `internal_draft` — publishing blocked
- `restricted_reference_only` — publishing blocked

OCR-imported content defaults to `internal_draft`. Admin must assign a publishable classification during review.

Documented in: OCR_IMPORT_PIPELINE.md, ADMIN_CONTENT_WORKFLOW.md, SECURITY_PRIVACY.md, PRD.md, DATA_MODEL.md

---

### [RESOLVED] AI Generated Question Policy

Decision: AI-generated questions supported, but cannot be auto-published.

Mandatory workflow: Draft → Review → Approved → Published. Admin approval is required at every stage without exception.

Documented in: PRD.md, ADMIN_CONTENT_WORKFLOW.md, AI_PROVIDER_STRATEGY.md, skills/ai-question-generation.md

---

### [RESOLVED] Selective Writing Support

Decision: Writing support is included in V1 for the Selective School exam.

- Writing prompts supported (narrative, persuasive, informative, imaginative)
- Timed writing supported
- Writing attempts stored as immutable records
- AI-assisted feedback supported (guidance only, not official marking)
- Mandatory disclaimer on all writing feedback:
  > "Writing feedback is educational guidance and does not represent official Selective School marking."

Documented in: PRD.md, EXAM_ENGINE.md, DATA_MODEL.md, AI_PROVIDER_STRATEGY.md, skills/writing-assessment.md, skills/nsw-selective-question-generation.md

---

### [RESOLVED] AI Skill System

Decision: Platform uses a structured AI skill system.

Skills documented:

- `skills/nsw-oc-question-generation.md`
- `skills/nsw-selective-question-generation.md`
- `skills/writing-assessment.md`
- `skills/question-quality-review.md`
- `skills/ai-question-generation.md` (updated)
- `skills/nsw-exam-domain.md` (updated)
- `skills/ocr-import-review.md` (updated)

Documented in: AI_PROVIDER_STRATEGY.md, ARCHITECTURE.md, skills/*.md

---

### [RESOLVED] AI Privacy Rules

Decision: Student personal information must not be sent to AI providers except where operationally necessary.

Explicit allowed and prohibited payload contents defined.
Two-category system: Category A (admin-only) and Category B (student-facing) with different requirements.

Documented in: SECURITY_PRIVACY.md, AI_PROVIDER_STRATEGY.md

---

### [RESOLVED] Future School Support

Decision: School functionality is NOT part of V1. Architecture must remain extensible.

Implementation:

- A nullable `organization_id` column is reserved on `ParentProfile`.
- No school features are implemented in V1.
- The future organization hierarchy is documented in DATA_MODEL.md section 9 as a planning reference.

Documented in: DATA_MODEL.md, ARCHITECTURE.md, OPEN_DECISIONS.md

---

## Open Decisions

These decisions are not required before Milestone 1 starts, but must be resolved before the relevant milestone.

### 1. Product Name

Working name: HSC Exam Platform.

Need final commercial name before public launch.

Required before: public launch (not M1)

---

### 2. Payment Provider

Options:

- Stripe
- Paddle

Recommendation: Stripe unless there is a specific business reason otherwise.

Required before: Milestone 5 (billing integration)

---

### 3. AI Production Provider

Development may use OpenAI or Ollama.

Production provider requires confirmed data processing agreement appropriate for Australian children's data.

DeepSeek is not approved. See AI_PROVIDER_STRATEGY.md.

Required before: Milestone 4 (AI provider layer)

---

### 4. OCR Engine Selection

Options:

- PaddleOCR (ARM64 compatible, text-focused)
- PaddleOCR + Pix2Text (adds maths formula handling)
- Tesseract (lighter weight alternative)

Recommendation: PaddleOCR for text; Pix2Text for maths-heavy content. Confirm ARM64 Docker image build before committing.

Required before: Milestone 6 (OCR pipeline)

---

### 5. Attempt History Retention Limit

Current suggestion: store up to 20 attempts per exam per student.

Need final retention and archival policy decision.

Required before: Milestone 4 (exam engine)

---

### 6. Mobile Phone Exam Mode Policy

Recommendation: allow account and report access; block or warn for full exam mode on screens narrower than 768px.

Need final minimum width threshold.

Required before: Milestone 4 (exam engine)

---

### 7. Subscription Tier Pricing

Tier names, prices, free trial duration, and feature gates have not been finalised.

Required before: Milestone 5 (billing integration)

---

### 8. Adaptive Learning Strategy

Recommendation: start rule-based (V1). Add AI-driven recommendations in V2+.

No decision required before M1.

---

### 9. Writing Assessment Rubric

The rubric used for Selective writing AI feedback has not been finalised.

Options:

- Generic writing rubric (created by the platform)
- NSW Selective-aligned rubric (requires legal review of NSW DoE marking criteria)

Required before: Milestone 4 (writing assessment feature)
