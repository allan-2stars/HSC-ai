# Writing Review Workflow (M5.1)

Human review lifecycle for submitted writing responses. This milestone implements
**human review only** — AI feedback generation, disputes, rubric scoring, and
reviewer balancing are explicitly out of scope and deferred.

## Principles

- The submission is **immutable** after submit (enforced by DB trigger). No review
  action ever mutates the submission row.
- Feedback lives in a **separate**, **versioned**, **append-only** table. The latest
  version is the current feedback. Rows are never updated or deleted (DB trigger).
- Feedback is **never visible to students or parents until published**. The publish
  step is a hard gate.
- All lifecycle actions are recorded in the existing `AuditLog`.
- Every feedback surface carries the mandatory disclaimer:
  > "Writing feedback is educational guidance and does not represent official Selective School marking."

## Data model

### `writing_reviews`

One row per submitted submission (unique on `submission_id`). Owns the review state.

| column | notes |
|---|---|
| `id` | uuid pk |
| `submission_id` | FK → `writing_submissions.id`, unique |
| `reviewer_admin_id` | FK → `admin_profiles.id`, nullable |
| `status` | `pending` / `assigned` / `under_review` / `reviewed` / `published` |
| `assigned_at` | set on assign |
| `review_started_at` | set when first opened |
| `published_at` | set on publish |
| `created_at`, `updated_at` | timestamps |

### `writing_feedback`

Versioned, append-only. Unique on `(review_id, version)`.

| column | notes |
|---|---|
| `id` | uuid pk |
| `review_id` | FK → `writing_reviews.id` |
| `version` | 1-based; increments per save |
| `overall_comment` | required free-form feedback |
| `dimensions` | optional JSON: `[{"name","comment"}]` — rubric-safe slot for the future |
| `created_by_admin_id` | FK → `admin_profiles.id`, nullable |
| `created_at` | timestamp |

Append-only is enforced by the `trg_writing_feedback_append_only` trigger, which
raises on any `UPDATE` or `DELETE`.

## State machine

```
  (student submits)
        │
        ▼
     pending ──assign──► assigned
        │                   │
        └──── open ─────────┴──► under_review
                                    │
                                 save feedback (adds version N)
                                    ▼
                                 reviewed ──publish──► published
```

| Transition | Trigger | Effect |
|---|---|---|
| → `pending` | student submits | review auto-created |
| → `assigned` | `POST /reviews/{id}/assign` | sets `reviewer_admin_id`, `assigned_at` |
| → `under_review` | first `GET /reviews/{id}` | sets `review_started_at` (idempotent after first open) |
| → `reviewed` | `POST /reviews/{id}/feedback` | inserts feedback version N |
| → `published` | `POST /reviews/{id}/publish` | sets `published_at`; **requires status `reviewed` + feedback exists** |

Guards:
- Publishing without feedback / before `reviewed` → `422`.
- Publishing an already-published review → `422`.
- Adding feedback after publish → `422` (re-opening is out of scope for M5.1).

## API

### Admin (`get_current_admin_profile`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/admin/writing/reviews` | Review queue. Optional `?status=`. |
| GET | `/api/v1/admin/writing/reviews/{id}` | Detail: submission content + latest feedback. Opens the review. |
| POST | `/api/v1/admin/writing/reviews/{id}/assign` | Self-assign reviewer. |
| POST | `/api/v1/admin/writing/reviews/{id}/feedback` | Add a feedback version. Body: `{overall_comment, dimensions?}`. |
| POST | `/api/v1/admin/writing/reviews/{id}/publish` | Publish to student/parent. |

### Student (`get_current_student`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/writing/submissions/{id}/feedback` | Latest **published** feedback for own submission. `404` if unpublished, `403` if not owner. |

### Parent (`get_current_parent`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/parents/students/{sid}/writing/{sub_id}/feedback` | Latest **published** feedback for own student. `403` if not their student, `404` if unpublished. |

The feedback response includes the mandatory `disclaimer` field.

## Auditing

Recorded in `AuditLog` (target_type `writing_review`):

| action | actor | metadata |
|---|---|---|
| `writing_review.created` | student | `{submission_id}` |
| `writing_review.opened` | admin | — |
| `writing_review.assigned` | admin | `{reviewer_admin_id}` |
| `writing_feedback.created` | admin | `{version}` |
| `writing_review.published` | admin | `{feedback_version}` |

## Frontend

- **Admin queue** — `/admin/writing/reviews` (status filters).
- **Admin review detail** — `/admin/writing/reviews/[reviewId]`: read submission,
  author feedback, publish (publish disabled until `reviewed`).
- **Student** — published feedback rendered on the submission page with disclaimer.
- **Parent** — published feedback expandable per submission on `/parent/writing`.

## Out of scope (deferred for M5.1)

AI feedback generation, disputes/appeals, numeric scoring/grading, reviewer
workload balancing. (Rubrics added in M5.2 — see below.)

---

# Writing Rubrics (M5.2)

Rubric-based assessment layered onto the human review workflow. Reviewers score a
submission against a rubric's dimensions (rating 1–5 + comment per dimension). The
rubric assessment is published and made visible under the same publish gate as the
overall feedback.

## Data model

### `writing_rubrics`
Reusable rubric template. `framework_id` / `subject_id` / `exam_type_id` are nullable
FKs (null = global/platform rubric); `active` boolean.

### `writing_rubric_dimensions`
`rubric_id` (FK, cascade delete), `name`, `description` (nullable), `display_order`.

### `writing_review_scores`
One row per `(review_id, dimension_id)` (unique). `rating` int with
`CheckConstraint(rating BETWEEN 1 AND 5)`, `comment` text. Editable while the review
is not published; rejected (422) once published — a future reopen/version workflow is
out of scope. Provenance: `created_by_admin_id` (nullable FK → `admin_profiles`) and
`source` (varchar, default `"human"`) — set on every write, reserved for future
AI-assisted scoring.

### `writing_tasks.rubric_id`
Nullable FK assigning a rubric to a task.

## Rating scale

`rating` is an integer 1–5, validated both at the API (`Field(ge=1, le=5)`) and the DB
(CheckConstraint). Display labels (mapped in the UI): 1 Needs Work, 2 Developing,
3 Satisfactory, 4 Strong, 5 Excellent.

## Publish gate

If the submission's task has an assigned rubric, publishing requires **every**
dimension to have a rating **and** a non-empty comment (else 422), in addition to the
M5.1 gate (status `reviewed` + overall feedback). Tasks with no rubric use the M5.1
gate unchanged.

## API

**Admin** (`get_current_admin_profile`):
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/admin/writing/rubrics` | Create rubric (optional inline dimensions) |
| GET | `/api/v1/admin/writing/rubrics` | List (`?active=`, `?framework_id=`) |
| GET | `/api/v1/admin/writing/rubrics/{id}` | Detail with dimensions |
| PATCH | `/api/v1/admin/writing/rubrics/{id}` | Edit rubric fields |
| POST | `/api/v1/admin/writing/rubrics/{id}/dimensions` | Add dimension |
| PATCH | `/api/v1/admin/writing/rubrics/{id}/dimensions/{dim_id}` | Edit dimension |
| DELETE | `/api/v1/admin/writing/rubrics/{id}/dimensions/{dim_id}` | Delete (422 if it has scores) |
| POST | `/api/v1/admin/writing/tasks/{task_id}/rubric` | Assign/clear rubric (`{rubric_id}` or null) — see assignment policy below |
| POST | `/api/v1/admin/writing/reviews/{id}/scores` | Upsert scores (`{scores:[{dimension_id,rating,comment}]}`) |

**Student / Parent** (published only, mirror the feedback endpoints):
| Method | Path |
|---|---|
| GET | `/api/v1/writing/submissions/{id}/rubric` |
| GET | `/api/v1/parents/students/{sid}/writing/{sub_id}/rubric` |

Both return `404` if unpublished/no rubric, `403` if not owned, and include the
mandatory `disclaimer`.

## Rubric assignment policy

`POST .../tasks/{id}/rubric` enforces:
- The rubric must exist, be **active**, and have **≥1 dimension** (else 422).
- Once any submission under the task has rubric scores, the rubric **cannot be changed
  or cleared** (422) — this protects assessment history. Re-assigning the *same*
  rubric is a no-op and always allowed. Old scores are never auto-deleted.

## Auditing (additions)

| action | actor | metadata |
|---|---|---|
| `writing_rubric.created` | admin | `{title}` |
| `writing_rubric.updated` | admin | dimension add: `{dimension_added}`; update: `{dimension_updated, previous, new}`; delete: `{dimension_deleted, deleted}` |
| `writing_task.rubric_assigned` | admin | `{rubric_id}` |
| `writing_review.scored` | admin | `{dimension_count}` |

Every rubric mutation — including dimension **update** and **delete** — is audited.

## Frontend (additions)

- **Admin rubrics** — `/admin/writing/rubrics`: list + create rubric with dimensions.
- **Admin review detail** — rubric scoring (rating select + comment per dimension).
- **Student / Parent** — published rubric assessment rendered alongside feedback.

## Out of scope (M5.2)

AI feedback, AI scoring, disputes, grade/aggregate calculations, reviewer balancing.

## Known limitations

- **No rubric snapshotting.** The published rubric assessment renders the *live*
  rubric/dimension text (`title`, `name`, `description`) joined to the historical
  `rating`/`comment`. Editing a rubric or dimension after publish therefore changes
  the labels a student/parent sees, while the scores stay as recorded. A future
  milestone should snapshot the rubric version onto the review (or store a
  `rubric_version` and immutable dimension copies) so published assessments are fully
  immutable — alongside the disputes/reopen workflow.
- Score immutability after publish is enforced at the service layer (not a DB trigger),
  consistent with the agreed M5.2 design.
