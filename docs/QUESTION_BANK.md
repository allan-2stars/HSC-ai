# Question Bank Architecture

## 1. Purpose

This document defines the complete content hierarchy for the HSC-AI platform, from atomic question content through to delivered exam instances and student attempt records.

The architecture is designed to:

- Separate reusable content (Question Bank) from exam structure (Exam Templates and Instances)
- Allow any question to be reused across multiple exam templates without duplication
- Preserve exact question version history so historical attempts always reference the content the student actually saw
- Support both fixed exams (predetermined question set) and dynamic exams (rule-based selection from pools)

---

## 2. Layer Overview

The content system has five distinct layers, each with a clearly bounded responsibility:

```
Layer 1: CONTENT
  Question           ← the root identity of a question
  QuestionVersion    ← immutable content snapshot (stem, options, answer, explanation)
  QuestionMedia      ← images and diagrams attached to a version

Layer 2: ORGANISATION
  QuestionPool       ← a named, logical grouping of questions

Layer 3: EXAM DESIGN
  ExamTemplate       ← the blueprint (structure, rules, configuration)
  ExamSection        ← an ordered section within a template (MCQ, writing)
  ExamSectionRule    ← how questions are selected for a section

Layer 4: EXAM DELIVERY
  ExamInstance       ← a specific published exam (questions frozen at publish time)
  ExamInstanceQuestion ← the exact QuestionVersion delivered in this instance

Layer 5: ATTEMPT
  Attempt            ← student session against an ExamInstance
  AttemptAnswer      ← student response linked to ExamInstanceQuestion + QuestionVersion
  WritingAttemptResponse ← student writing response (immutable after submission)
  AttemptIntegrityEvent  ← security event log
```

The critical invariant:

> An `AttemptAnswer` always references a `QuestionVersion`, never a `Question`. This ensures the historical record is accurate even if the question is later edited or archived.

---

## 3. Entity Reference

### Layer 1: Content

#### Question

The root identity of a piece of content. Holds metadata that persists across all versions.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| subject_id | uuid | FK → Subject |
| exam_type_id | uuid | FK → ExamType |
| year_level | smallint | 4, 5, or 6 |
| topic_id | uuid | FK → Topic |
| skill_tag_ids | uuid[] | Array FK → SkillTag |
| difficulty | enum | easy \| medium \| hard |
| question_type | enum | mcq \| short_answer \| extended_response |
| status | enum | draft \| review \| approved \| published \| archived \| rejected |
| source_type | enum | manual \| ocr \| ai |
| content_ownership | enum | See ContentOwnershipType in DATA_MODEL.md |
| copyright_note | text | Optional attribution or restriction note |
| current_version_id | uuid | FK → QuestionVersion (latest active version) |
| created_by_admin_id | uuid | FK → AdminProfile |
| created_at | timestamptz | |
| updated_at | timestamptz | |

Publishing constraint: Questions with `content_ownership` of `internal_draft` or `restricted_reference_only` cannot be set to `published`.

#### QuestionVersion

An immutable snapshot of question content at a point in time. Once created, a version is never modified.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| question_id | uuid | FK → Question |
| version_number | integer | Auto-incrementing per question |
| stem | text | The question text |
| correct_answer | text | For MCQ: the label (A/B/C/D). For structured: the expected value. |
| full_explanation | text | Required. Must explain why the answer is correct. |
| marks | smallint | Point value |
| options_json | jsonb | MCQ options: [{label, text, is_correct, explanation}] |
| metadata_json | jsonb | Flexible metadata (source page, OCR confidence, etc.) |
| created_by_admin_id | uuid | FK → AdminProfile |
| created_at | timestamptz | |

Rules:

- Versions are created, never updated.
- When an admin edits an approved question, a new version is created and becomes `current_version_id`.
- Old versions are retained permanently for historical attempt accuracy.

#### QuestionMedia

Images, diagrams, or audio attached to a specific question version.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| question_version_id | uuid | FK → QuestionVersion |
| storage_key | text | MinIO object path |
| media_type | enum | image \| audio |
| caption | text | Optional alt text / description |
| sort_order | smallint | Display order |

---

### Layer 2: Organisation

#### QuestionPool

A named, logical grouping of questions. Used for dynamic exam section assembly.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| name | text | Descriptive name |
| description | text | Optional |
| subject_id | uuid | Optional FK → Subject (for filtering) |
| exam_type_id | uuid | Optional FK → ExamType |
| year_level | smallint | Optional filter |
| pool_type | enum | static \| dynamic |
| query_criteria_json | jsonb | For dynamic pools: filter rules (topic, difficulty, year_level, etc.) |
| created_by_admin_id | uuid | |
| created_at | timestamptz | |

Two pool types:

- **Static pool**: Admin explicitly selects which questions are members.
- **Dynamic pool**: Membership is derived at exam-generation time from query criteria. V1 may implement static only; dynamic is a future feature.

#### QuestionPoolMembership

Junction table for static pool membership.

Fields:

| Field | Type | Notes |
|---|---|---|
| pool_id | uuid | FK → QuestionPool |
| question_id | uuid | FK → Question |
| added_at | timestamptz | |
| added_by_admin_id | uuid | |

Primary key: (pool_id, question_id)

---

### Layer 3: Exam Design

#### ExamTemplate

The reusable blueprint defining the structure and rules of an exam. A template can be instantiated multiple times (e.g., for different years, cohorts, or variants).

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| title | text | |
| description | text | |
| exam_type_id | uuid | FK → ExamType |
| subject_id | uuid | Optional — null for multi-subject exams |
| year_level | smallint | |
| total_duration_seconds | integer | Overall time limit |
| mode | enum | fixed \| dynamic |
| status | enum | draft \| active \| retired |
| created_by_admin_id | uuid | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

#### ExamSection

An ordered section within an exam template. Sections can have independent time limits.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| template_id | uuid | FK → ExamTemplate |
| title | text | |
| section_type | enum | mcq \| writing |
| order_index | smallint | Section order |
| duration_seconds | integer | Optional section-level time limit |
| instructions | text | Displayed to student before section starts |

#### ExamSectionRule

Defines how questions are selected for a section within a fixed or dynamic exam.

For fixed exams: references explicit QuestionVersion IDs.
For dynamic exams: references a QuestionPool with a count and optional criteria.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| section_id | uuid | FK → ExamSection |
| rule_type | enum | fixed_question \| pool_draw |
| question_version_id | uuid | FK → QuestionVersion (for fixed_question rules) |
| pool_id | uuid | FK → QuestionPool (for pool_draw rules) |
| draw_count | smallint | How many questions to draw from pool |
| order_index | smallint | Position within section |
| marks | smallint | Override marks for this position (if different from QuestionVersion) |

---

### Layer 4: Exam Delivery

#### ExamInstance

A specific published exam. For fixed exams, the question set is frozen at creation time. For dynamic exams, the question set is generated at creation time from pool rules.

An ExamInstance is what students actually take.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| template_id | uuid | FK → ExamTemplate |
| title | text | May override template title |
| status | enum | draft \| published \| closed \| archived |
| available_from | timestamptz | Optional: start of availability window |
| available_until | timestamptz | Optional: end of availability window |
| created_by_admin_id | uuid | |
| published_at | timestamptz | |
| created_at | timestamptz | |

#### ExamInstanceQuestion

The exact set of questions in this exam instance, in delivery order. This table is frozen at publish time and never modified.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| instance_id | uuid | FK → ExamInstance |
| section_id | uuid | FK → ExamSection |
| question_version_id | uuid | FK → QuestionVersion (frozen at publish time) |
| order_index | smallint | Global delivery order |
| section_order_index | smallint | Order within section |
| marks | smallint | |

Rules:

- Records are created when an ExamInstance is published.
- Records are never modified after publication.
- All student attempts reference `ExamInstanceQuestion.question_version_id` directly, preserving the exact content seen.

---

### Layer 5: Attempt

#### Attempt

A student's session against an ExamInstance.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| student_id | uuid | FK → StudentProfile |
| instance_id | uuid | FK → ExamInstance |
| status | enum | in_progress \| submitted \| auto_submitted \| abandoned |
| started_at | timestamptz | UTC — server-authoritative |
| submitted_at | timestamptz | Set once, never changed |
| duration_seconds | integer | Actual elapsed time at submission |
| score | numeric | Calculated at submission |
| max_score | numeric | From ExamInstance |
| integrity_summary_json | jsonb | Aggregate of integrity events |

Rules:

- Submitted attempts are immutable. A DB trigger enforces this.
- Retakes create new Attempt records; they never overwrite prior attempts.
- Students cannot delete Attempt records.

#### AttemptAnswer

The student's response to a specific question in the attempt.

Fields:

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| attempt_id | uuid | FK → Attempt |
| exam_instance_question_id | uuid | FK → ExamInstanceQuestion |
| question_version_id | uuid | FK → QuestionVersion (denormalised from ExamInstanceQuestion for direct query access) |
| answer_value | text | The student's selected option or entered value |
| is_correct | boolean | Calculated at submission |
| marks_awarded | numeric | |
| answered_at | timestamptz | |
| time_spent_seconds | integer | |

Note: `question_version_id` is denormalised here intentionally. It allows direct analytics queries against question performance without joining through ExamInstanceQuestion. It must always match `ExamInstanceQuestion.question_version_id`.

---

## 4. Lifecycle Diagrams

### Question Version Lifecycle

```
Admin creates question
        ↓
   QuestionVersion v1 created
   Question.current_version_id = v1
   Question.status = draft
        ↓
   Admin submits for review
   Question.status = review
        ↓
   Admin approves
   Question.status = approved
        ↓
   Admin publishes to exam set
   Question.status = published
        ↓
   Admin finds error → edits question
        ↓
   QuestionVersion v2 created
   Question.current_version_id = v2
   Question.status = review (re-enters review)
        ↓
   Previous ExamInstanceQuestion records still reference v1
   New ExamInstanceQuestion records will reference v2
        ↓
   All AttemptAnswers referencing v1 remain valid and correct
```

### Exam Template to Instance Lifecycle

```
Admin creates ExamTemplate
        ↓
Admin creates ExamSections
        ↓
Admin adds ExamSectionRules
  (fixed questions or pool references)
        ↓
Admin creates ExamInstance from Template
        ↓
System resolves all section rules:
  - Fixed rules → copy QuestionVersion references
  - Pool rules → draw questions from pool, freeze selection
        ↓
ExamInstanceQuestion records created (frozen)
ExamInstance.status = draft
        ↓
Admin reviews and publishes instance
ExamInstance.status = published
        ↓
Students can now start Attempts against this ExamInstance
```

### Attempt Lifecycle

```
Student selects ExamInstance
        ↓
Entitlement check (subscription, year level)
        ↓
Attempt created (status = in_progress)
started_at = UTC now (server)
        ↓
Student answers questions
AttemptAnswer records upserted per question
        ↓
Student submits OR timer expires (auto_submit)
        ↓
Server calculates score from AttemptAnswers
Attempt.status = submitted | auto_submitted
Attempt.submitted_at = UTC now
        ↓
DB trigger fires: DENY any future UPDATE to this Attempt
        ↓
Results and explanations displayed to student and parent
```

---

## 5. ERD (Entity Relationship Diagram)

```
Subject ──────────────────┐
ExamType ─────────────────┤
Topic ─────────────────── ├──► Question ──► QuestionVersion ──► QuestionMedia
SkillTag ─────────────────┘         │
                                    │
                                    ▼
                            QuestionPoolMembership
                                    ▲
                            QuestionPool ◄── ExamSectionRule (pool_draw)
                                                │
                            ExamTemplate        │
                               └── ExamSection ─┘
                                      │
                                      └── ExamSectionRule (fixed_question)
                                                │
                                                ▼
                                         QuestionVersion
                                                │
                                                ▼
                                         ExamInstance
                                            │  └── ExamInstanceQuestion
                                            │              │
                                            ▼              ▼
                                         Attempt ──► AttemptAnswer
                                            │   (references QuestionVersion)
                                            ├──► WritingAttemptResponse
                                            └──► AttemptIntegrityEvent
```

---

## 6. Key Design Decisions

### Decision: ExamTemplate vs ExamInstance

**Template** is the reusable design. **Instance** is a specific, frozen delivery.

A single template can produce multiple instances over time (e.g., "Year 5 OC Maths Practice" as a template, with refreshed instances each term using different question selections from the same pool).

For V1, every template will produce exactly one active instance. The distinction is worth preserving now to avoid a painful schema migration when multi-instance or adaptive delivery is needed.

### Decision: QuestionVersion is the atomic delivery unit

Exams and attempts never reference a `Question` directly — they always reference a `QuestionVersion`. This means:

- An admin can update a question (creating a new version) without invalidating past exam results.
- A question can be updated mid-term; old instances continue using the old version; new instances use the new version.
- A student who retakes an exam after a question was updated will see the updated content in a new instance.

### Decision: ExamInstanceQuestion freezes the question set at publish time

Once an ExamInstance is published, its `ExamInstanceQuestion` records are immutable. The question set students see is determined at publish time, not at attempt time. This prevents a scenario where an admin publishes a new question version mid-exam-window and students get different content.

### Decision: AttemptAnswer.question_version_id is denormalised

Although `question_version_id` is derivable via `exam_instance_question_id`, it is stored directly on `AttemptAnswer` for analytics performance. Aggregating question performance across many attempts without this denormalisation would require two joins on every query. The redundancy is intentional and must be kept in sync by the application layer on insert.

---

## 7. Question Reuse Rules

A single `Question` (and its versions) can be referenced by:

- Multiple `QuestionPool` memberships
- Multiple `ExamSectionRule` fixed references
- Multiple `ExamInstanceQuestion` records across different exam instances

This is intentional and expected. A well-written Year 5 fractions MCQ should appear in both OC and Selective practice sets if appropriate.

There is no restriction on reuse, but admins should be aware that:

- Updating a question (new version) affects all future instances, not past ones.
- If the same question appears twice in the same exam instance, this should be prevented at the admin UI layer (a warning, not a hard constraint in V1).

---

## 8. V1 Scope Boundary

V1 implements:

- Question, QuestionVersion, QuestionMedia
- QuestionPool (static only)
- ExamTemplate, ExamSection, ExamSectionRule (fixed_question mode)
- ExamInstance, ExamInstanceQuestion
- Attempt, AttemptAnswer, WritingAttemptResponse, AttemptIntegrityEvent

V1 defers:

- Dynamic pool (query-based question selection)
- Multi-instance adaptive delivery (generating personalised exam instances per student)
- Pool-draw section rules (random selection from pool at instance creation)
