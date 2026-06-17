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

## Out of scope (deferred)

AI feedback generation, disputes/appeals, rubric tables, numeric scoring/grading,
reviewer workload balancing.
