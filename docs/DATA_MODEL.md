# Data Model Specification

This document defines the core domain model. Exact schema can evolve, but implementation should preserve these domain boundaries.

## 1. Users and Roles

### User

Fields:

- id
- email
- password_hash or external_auth_id
- role: parent | student | admin
- status
- created_at
- updated_at

### ParentProfile

Fields:

- id
- user_id
- display_name
- max_students: default 3

### StudentProfile

Fields:

- id
- user_id
- parent_id
- display_name
- year_level
- date_of_birth optional
- status

Constraint:

- A parent can have maximum 3 active student profiles in V1.

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
- status
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
- parent_topic_id optional

### SkillTag

Fields:

- id
- topic_id
- name
- slug

## 4. Questions

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
- created_by_admin_id
- created_at
- updated_at

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
- explanation optional

## 5. Exams

### Exam

Fields:

- id
- title
- exam_type_id
- subject_id optional
- year_level
- duration_seconds
- status: draft | published | archived
- mode: fixed | dynamic
- created_by_admin_id
- created_at
- updated_at

### ExamSection

Fields:

- id
- exam_id
- title
- order_index
- duration_seconds optional

### ExamQuestion

Fields:

- id
- exam_id
- section_id
- question_id
- order_index
- marks

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

### AttemptAnswer

Fields:

- id
- attempt_id
- question_id
- question_version_id
- answer_value
- is_correct
- marks_awarded
- answered_at
- time_spent_seconds

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
- status
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
- page_image_storage_key optional

### ContentReviewItem

Fields:

- id
- source_type: manual | ocr | ai
- source_file_id optional
- ocr_job_id optional
- proposed_question_json
- status: needs_review | approved | rejected | published
- reviewed_by_admin_id optional
- reviewed_at optional

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
- user_id optional
- admin_id optional
- provider_name
- feature
- tokens_in
- tokens_out
- cost_estimate
- created_at
