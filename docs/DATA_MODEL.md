# Data Model Specification

This document defines the core domain model. Exact schema can evolve, but implementation should preserve these domain boundaries.

## 1. Users and Roles

### User

Fields:

- id
- email
- password_hash
- role: parent | student | admin
- status: active | suspended | deleted
- created_at
- updated_at

### ParentProfile

Fields:

- id
- user_id
- display_name
- max_students: default 3
- organization_id (nullable — reserved for future school/tutor support; null for all V1 users)

### StudentProfile

Fields:

- id
- user_id
- parent_id (required — student accounts cannot exist without a parent)
- display_name
- year_level
- date_of_birth (optional)
- status: active | suspended | deleted
- first_login_completed: boolean, default false

Constraint:

- A parent can have maximum 3 active student profiles in V1.
- A StudentProfile must have a valid parent_id. Orphaned student records are not permitted.

### Family Account Model

Students are subordinate accounts within a parent's family account.

Rules:

- Parent creates student accounts; students do not self-register.
- On first login, the student must set their own password before accessing any exams.
- Parent can reset a student's password at any time.
- Student cannot modify their own parent linkage.
- Student cannot access billing, subscription, or parent account settings.
- Deleting a parent account archives all linked student accounts and their attempt history.

Student account capabilities:

| Capability | Student Allowed |
|---|---|
| Take exams | Yes |
| Review own attempts | Yes |
| View own progress | Yes |
| Access billing | No |
| Manage subscription | No |
| Delete attempt history | No |
| Change own parent linkage | No |
| Register without parent | No |

### AdminProfile

Fields:

- id
- user_id
- display_name

MVP:

- All admins share the same permission level.

## 2. Subscription and Entitlement

### Subscription

Fields:

- id
- parent_id
- plan_id
- billing_period: monthly | annual
- status: trialing | active | past_due | cancelled | paused
- starts_at
- ends_at
- renews_at

### Plan

Fields:

- id
- name
- type: all_access | subject | exam_type
- billing_period
- price
- is_premium

### Entitlement

Fields:

- id
- subscription_id
- scope_type: all_access | subject | exam_type
- scope_value
- starts_at
- ends_at

## 3. Curriculum and Content

### Subject

Fields:

- id
- name
- slug

Examples:

- Mathematics
- English
- Thinking Skills
- Science

### ExamType

Fields:

- id
- name
- slug

Examples:

- OC
- Selective
- NAPLAN
- HSC

### Topic

Fields:

- id
- subject_id
- name
- slug
- parent_topic_id (optional, for nested topics)

### SkillTag

Fields:

- id
- topic_id
- name
- slug

## 4. Questions

### ContentOwnershipType

Enumerated values for content ownership classification:

- `original` — written directly by a platform admin
- `licensed` — third-party content with a confirmed licence agreement
- `public_domain` — confirmed as public domain
- `approved_internal` — internal draft promoted through full review
- `user_provided_with_rights` — submitted by a party who has declared rights ownership
- `internal_draft` — pending copyright review; cannot be published
- `restricted_reference_only` — copyright-restricted; for admin reference only; cannot be published

### Question

Fields:

- id
- current_version_id
- subject_id
- exam_type_id
- year_level
- topic_id
- difficulty: easy | medium | hard
- status: draft | review | approved | published | archived | rejected
- source_type: manual | ocr | ai
- content_ownership: ContentOwnershipType (required on all questions)
- copyright_note (optional — licence attribution, source credit, or restriction reason)
- created_by_admin_id
- created_at
- updated_at

Publishing constraint:

- Questions with `content_ownership` of `internal_draft` or `restricted_reference_only` cannot be set to `published` regardless of review status.

### QuestionVersion

Fields:

- id
- question_id
- version_number
- stem
- correct_answer
- full_explanation
- marks
- metadata_json
- created_by_admin_id
- created_at

### QuestionOption

Fields:

- id
- question_version_id
- label
- text
- is_correct
- explanation (optional)

## 5. Exams

### Exam

Fields:

- id
- title
- exam_type_id
- subject_id (optional)
- year_level
- duration_seconds
- status: draft | published | archived
- mode: fixed | dynamic
- has_writing_section: boolean, default false
- created_by_admin_id
- created_at
- updated_at

### ExamSection

Fields:

- id
- exam_id
- title
- order_index
- duration_seconds (optional)
- section_type: mcq | writing

### ExamQuestion

Fields:

- id
- exam_id
- section_id
- question_id
- order_index
- marks

### WritingPrompt

Fields:

- id
- exam_id
- section_id
- prompt_text
- prompt_type: narrative | persuasive | informative | imaginative
- word_limit (optional)
- marks
- time_limit_seconds (optional, overrides section time if set)
- created_by_admin_id
- created_at

## 6. Attempts

### Attempt

Fields:

- id
- student_id
- exam_id
- status: in_progress | submitted | auto_submitted | abandoned
- started_at
- submitted_at
- duration_seconds
- score
- max_score
- integrity_summary_json

Rules:

- Submitted attempts are immutable.
- Attempts are never overwritten by retakes.
- Students cannot delete attempts.
- Parents may archive attempts according to retention policy.

### AttemptAnswer

Fields:

- id
- attempt_id
- question_id
- question_version_id (references the exact version seen during the attempt)
- answer_value
- is_correct
- marks_awarded
- answered_at
- time_spent_seconds

### WritingAttemptResponse

Fields:

- id
- attempt_id
- writing_prompt_id
- response_text (the student's written response — stored immutably after submission)
- word_count
- time_spent_seconds
- submitted_at

Rules:

- Writing responses are immutable after attempt submission.
- Response text is stored verbatim as entered.

### WritingFeedback

Fields:

- id
- writing_attempt_response_id
- ai_provider
- feedback_text
- criteria_scores_json (rubric breakdown if available)
- generated_at
- model_version (optional, for audit)

Rules:

- Writing feedback is AI-generated guidance only.
- It does not represent official Selective School marking.
- Feedback is stored for reference but is not part of the immutable attempt record.
- This disclaimer must appear in all UI surfaces that display WritingFeedback:
  > "Writing feedback is educational guidance and does not represent official Selective School marking."

### AttemptIntegrityEvent

Fields:

- id
- attempt_id
- event_type
- event_data_json
- occurred_at

Examples:

- fullscreen_exit
- tab_blur
- tab_focus
- copy_attempt
- paste_attempt
- right_click_attempt

## 7. OCR and Review

### SourceFile

Fields:

- id
- uploaded_by_admin_id
- file_name
- file_type
- storage_key
- checksum
- uploaded_at

### OCRJob

Fields:

- id
- source_file_id
- status: queued | processing | needs_review | failed | completed
- ocr_engine
- started_at
- completed_at
- error_message

### OCRPageResult

Fields:

- id
- ocr_job_id
- page_number
- extracted_text
- confidence
- page_image_storage_key (optional)

### ContentReviewItem

Fields:

- id
- source_type: manual | ocr | ai
- source_file_id (optional)
- ocr_job_id (optional)
- proposed_question_json
- content_ownership: ContentOwnershipType (must be assigned before approval)
- status: needs_review | approved | rejected | published
- reviewed_by_admin_id (optional)
- reviewed_at (optional)

## 8. AI Usage

### AIProviderConfig

Fields:

- id
- provider_name
- enabled
- purpose
- config_json

### AIUsageLog

Fields:

- id
- user_id (optional — null for admin-only operations)
- admin_id (optional)
- provider_name
- feature
- tokens_in
- tokens_out
- cost_estimate
- payload_contained_student_data: boolean (for privacy audit)
- created_at

Note: The `payload_contained_student_data` flag supports periodic privacy audits to confirm that student personal data is not being sent to AI providers except where explicitly intended.

## 9. Analytics Entities

These entities support future recommendation and weakness analysis features. They are designed to be populated progressively as students take exams. V1 should create the tables and populate `QuestionAttempt` records on attempt submission. `TopicPerformance` and `StudentSkillScore` may be computed in background jobs in V2+.

Do not implement analytics UI or recommendation features in V1. Lay the data foundation only.

### QuestionAttempt

A denormalised record of a student's interaction with a single question. Created for each `AttemptAnswer` on submission. Enables per-question performance analytics without querying the full attempt tree.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| student_id | uuid | FK → StudentProfile |
| question_id | uuid | FK → Question (the root question identity) |
| question_version_id | uuid | FK → QuestionVersion (the exact version answered) |
| attempt_id | uuid | FK → Attempt |
| answered_correctly | boolean | Copied from AttemptAnswer.is_correct |
| time_taken_seconds | integer | Time spent on this question |
| created_at | timestamptz | UTC — mirrors AttemptAnswer.answered_at |

Rules:

- One record per AttemptAnswer, created at attempt submission time.
- Never updated. If an attempt is reanalysed, insert a new record; do not update existing ones.
- `question_id` is denormalised from `question_version_id` for simpler per-question aggregation queries.

### TopicPerformance

An aggregated summary of a student's performance within a topic. Updated (or recalculated) when new QuestionAttempt records are inserted for the student.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| student_id | uuid | FK → StudentProfile |
| topic_id | uuid | FK → Topic |
| attempts | integer | Total questions attempted in this topic |
| correct_count | integer | Total correct answers |
| accuracy_rate | numeric(5,2) | correct_count / attempts × 100 |
| average_time_seconds | numeric(6,1) | Average time per question in this topic |
| last_updated_at | timestamptz | When this aggregate was last recalculated |

Rules:

- One record per (student_id, topic_id) combination.
- Updated incrementally or recalculated from QuestionAttempt records.
- `accuracy_rate` is a computed/stored value; it must be kept consistent with `attempts` and `correct_count`.
- Used by the parent dashboard weakness summary in V1 (rule-based, not AI).

### StudentSkillScore

A higher-level skill proficiency estimate. Computed from TopicPerformance and QuestionAttempt data. Intended for future AI-powered recommendation features; populated by a background job.

In V1, this table is created but may remain empty. It is populated when the recommendation engine is implemented (V2+).

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| student_id | uuid | FK → StudentProfile |
| skill_name | text | Matches SkillTag.name or a computed skill label |
| score | numeric(5,2) | Proficiency score, 0–100 |
| confidence | numeric(4,3) | Model confidence in the score, 0–1. Low confidence = insufficient data. |
| evidence_count | integer | Number of QuestionAttempt records used to compute this score |
| last_calculated_at | timestamptz | When the score was last computed |

Rules:

- One record per (student_id, skill_name) combination.
- Scores with `evidence_count < 5` should be treated as unreliable and not surfaced in UI.
- `confidence` below 0.5 should trigger a "not enough data" display rather than showing the score.
- Scores are recalculated by a background job; they are not updated in-line during exam submission.

### Analytics Usage in V1

In V1, analytics are rule-based SQL queries over `QuestionAttempt` and `TopicPerformance`. No AI involvement.

V1 parent dashboard queries:

```
Score trend:
  SELECT attempt.submitted_at, attempt.score_pct
  FROM attempts
  WHERE student_id = :student_id
  ORDER BY submitted_at DESC
  LIMIT 10

Weakest topics:
  SELECT topic.name, tp.accuracy_rate, tp.attempts
  FROM topic_performance tp
  JOIN topics topic ON tp.topic_id = topic.id
  WHERE tp.student_id = :student_id
    AND tp.attempts >= 5
  ORDER BY tp.accuracy_rate ASC
  LIMIT 5

Time vs. accuracy:
  SELECT AVG(time_taken_seconds), AVG(CASE WHEN answered_correctly THEN 1 ELSE 0 END)
  FROM question_attempts
  WHERE student_id = :student_id
    AND created_at > NOW() - INTERVAL '30 days'
```

AI-powered recommendations are deferred until TopicPerformance data is meaningful (≥500 QuestionAttempt records per subject).

## 10. Future Extensions (Not V1)

### Organization (reserved for school/tutor support)

This table is not implemented in V1. It is documented here as a planning reference.

The `organization_id` field on `ParentProfile` (nullable) is reserved to support this future relationship without requiring a schema migration.

Proposed future structure:

```text
Organization
  └── Staff/Teacher (org admin role)
       └── Class or Group
            └── Students (organization-linked)
```

Fields (future):

- id
- name
- type: school | tutoring_centre | enterprise
- contact_email
- billing_model
- created_at

When implemented, a student can be linked to either a parent account, an organization, or both. V1 students are always parent-linked.
