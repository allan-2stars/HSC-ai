# AI Provider Strategy

## 1. Purpose

The system must support AI-assisted features without coupling business logic to a single model provider.

The AI layer must be provider-independent and switchable via configuration.

## 2. Supported Provider Targets

Approved providers:

- OpenAI
- Claude (Anthropic)
- Ollama (local/self-hosted)
- OpenRouter (routing aggregator — see caution below)

Development default:

- OpenAI or a locally hosted Ollama model during development

Production default:

- Must be explicitly configured via environment variable
- Must be a provider with an appropriate data processing agreement for use with student data

### Provider Caution: DeepSeek

DeepSeek is not approved for use in this platform with student data or in production.

Reason: DeepSeek is subject to data localisation requirements under PRC law. These requirements are incompatible with the platform's obligations under APP 8 of the Australian Privacy Act 1988, which requires overseas disclosure of personal information to meet equivalent Australian Privacy Principles standards.

DeepSeek may be evaluated for admin-only, non-student-data contexts with explicit legal sign-off, but is not an approved default.

### Provider Caution: OpenRouter

OpenRouter routes requests to multiple underlying providers. The data handling policy of the final provider receiving the request may not meet Australian Privacy Principles requirements. Use OpenRouter only for admin-only features where no student data is involved, and document which underlying provider is being used.

### Provider Caution: Gemini (Google)

Gemini may be used for admin features. Review Google's current data processing agreements and opt-out of training data usage before use with any student content.

## 3. AI Use Cases

### Admin Features

- OCR structure extraction
- AI-generated draft questions
- Explanation drafting
- Topic and difficulty tagging assistance
- Writing prompt quality review
- Question quality review

### Premium Student/Parent Features

- Weakness analysis
- Practice recommendations
- AI tutor explanation
- Writing feedback (Selective School)
- Readiness summary

## 4. AI Skill System

The platform uses a structured skill system to define AI responsibilities and quality standards. Skills are documented in the `skills/` directory.

### Current Skills

| Skill | File | Purpose |
|---|---|---|
| NSW OC Question Generation | `skills/nsw-oc-question-generation.md` | Generate draft OC exam questions |
| NSW Selective Question Generation | `skills/nsw-selective-question-generation.md` | Generate draft Selective exam questions including writing prompts |
| Writing Assessment | `skills/writing-assessment.md` | Provide AI-assisted feedback on writing responses |
| Question Quality Review | `skills/question-quality-review.md` | Review drafted questions for quality before admin approval |
| AI Question Generation (general) | `skills/ai-question-generation.md` | General rules for AI question generation |
| Exam Content Design | `skills/exam-content-design.md` | Principles for designing exam content |
| NSW Exam Domain | `skills/nsw-exam-domain.md` | Domain knowledge rules for NSW exam content |
| OCR Import Review | `skills/ocr-import-review.md` | Rules for OCR import and review workflow |

### Skill Responsibilities

Each skill defines:

- Input requirements (what the AI receives)
- Output format (what the AI must return)
- Quality standards (what constitutes acceptable output)
- Privacy constraints (what must not be included in the payload)

Business services must call AI through the skill abstraction. Skills must not be bypassed to call providers directly.

## 5. Provider Abstraction

Business services call an internal interface. The provider router decides which backend model to use based on configuration.

Core interface methods:

- `generate_question_draft` — produces a draft question for admin review
- `generate_explanation` — drafts an explanation for a question
- `extract_questions_from_ocr` — structures OCR text into question format
- `analyze_weakness` — summarizes student performance pattern
- `recommend_practice` — suggests practice content based on performance
- `assess_writing` — returns feedback on a writing response against a rubric

No business route handler should import or call an AI provider SDK directly.

## 6. AI Privacy Rules

### Two Categories of AI Use

AI features fall into two distinct categories with different privacy requirements:

**Category A: Admin-only AI (question generation, OCR extraction)**

- No student personal data involved.
- Admin provides a prompt: subject, topic, difficulty, year level.
- Any provider may be used with standard data handling.

**Category B: Student-facing AI (writing feedback, weakness analysis)**

- May involve student response content.
- Must not include student personal information.
- Provider must have a valid data processing agreement.
- Log each request with `payload_contained_student_data = true`.

### Allowed in AI Payloads

The following are permitted in AI provider requests:

- Prompt text (question or writing prompt)
- Student response text (writing content, answers — for assessment only)
- Rubric or marking criteria
- Year level (e.g., Year 5)
- Exam type (e.g., OC, Selective)
- Topic or subject label
- Question difficulty
- Generic performance pattern (e.g., percentage correct by topic)
- Anonymized question IDs

### Prohibited from AI Payloads

The following must never appear in AI provider requests:

- Student full name
- Student date of birth
- Parent name or identity
- Parent email address
- Billing or payment information
- Subscription plan details
- Contact details of any kind
- School name or location
- Any combination of fields that could re-identify a student

## 7. Writing Assessment

Writing assessment is a V1 AI feature for the Selective School writing component.

The AI:

- Receives: writing prompt, student response, rubric, year level, exam type
- Returns: structured feedback covering content, vocabulary, structure, and style
- Does not: assign an official mark or grade

All writing feedback must display the following disclaimer in every UI surface:

> "Writing feedback is educational guidance and does not represent official Selective School marking."

Writing feedback is stored in the `WritingFeedback` table linked to the student's attempt response. It is not part of the immutable attempt record and does not affect the attempt score.

## 8. AI Generated Content Policy

AI-generated content is always a draft.

The mandatory workflow is:

```text
Draft (AI generated)
  ↓
Review (admin mandatory — no exceptions)
  ↓
Approved
  ↓
Published
```

Auto-publishing is not permitted for any AI-generated content. This applies to:

- Generated questions
- Generated explanations
- Structured questions extracted from OCR
- Any AI-structured content

## 9. Logging

AI usage must log:

- Provider name
- Feature or skill invoked
- User/admin scope
- Token estimate (input and output)
- Error status
- Cost estimate
- `payload_contained_student_data` boolean

Do not log raw prompt text unless explicitly required for debugging and protected under access controls.

## 10. Premium Gating

AI features are Premium-only unless limited trial usage is configured.

Examples:

- Limited free AI explanations per month
- Limited recommendations per week
- Writing feedback available to premium subscribers

## 11. Non-Goals for MVP

- Fully autonomous AI tutoring without guardrails.
- AI-generated content auto-publishing.
- AI long-answer marking for HSC.
- Autonomous AI writing assessment without admin configuration of rubric.
