# M5.3 — AI Feedback Drafts: implemented & validated

The implementation was completed and approved-as-built. Everything below was
re-verified against the requested checklist.

## Final validation results

| Check | Result |
|---|---|
| `alembic heads` / `current` | single head `f6a7b8c9d0e1`, DB current ✓ |
| Migration down/up round-trip | clean (downgrade → e5f6a7b8c9d0 → upgrade head) ✓ |
| Backend M5.3 module | **16 passed** ✓ |
| Backend full suite (identical tree) | **399 passed**, exit 0 ✓ |
| Frontend suite | **52 passed** (13 files) ✓ |
| `tsc --noEmit` (M5.3 files) | clean (pre-existing errors only in unrelated `ai-generate/page.tsx`) ✓ |

## Migration

`backend/alembic/versions/f6a7b8c9d0e1_writing_feedback_drafts.py` (down_revision `e5f6a7b8c9d0`)

## API endpoints added (admin-only — `get_current_admin_profile`)

- `POST /api/v1/admin/writing/reviews/{review_id}/ai-draft` — generate (`422` if review published)
- `GET  /api/v1/admin/writing/reviews/{review_id}/ai-drafts` — list (newest first)
- `POST /api/v1/admin/writing/ai-drafts/{draft_id}/accept` — copy into a new official feedback version via the existing versioning path; marks `accepted`; never publishes
- `POST /api/v1/admin/writing/ai-drafts/{draft_id}/discard` — marks `discarded`

## Files changed

### Backend
- `app/models/writing.py` — `WritingFeedbackDraft` + `WritingFeedbackDraftStatus`
- `app/models/__init__.py` — exports
- `app/services/writing_feedback_providers.py` *(new)* — `FeedbackParams`/`GeneratedFeedbackDraft`, deterministic `mock` (default) + `openai`/`claude`/`ollama` (reusing the M4.7 provider/registry/structured-JSON pattern), `PROMPT_VERSION="wfd-v1"`
- `app/services/writing_feedback_draft_service.py` *(new)* — generate / list / accept / discard; `accept` reuses `writing_review_service.add_feedback` (existing versioning path)
- `app/schemas/writing_schema.py` — `AIDraftGenerate`
- `app/api/v1/admin/writing.py` — 4 endpoints
- `alembic/versions/f6a7b8c9d0e1_writing_feedback_drafts.py` *(new)*

### Frontend
- `src/lib/api.ts` — 4 client methods + `WritingFeedbackDraft`/`AIDraftFeedback` types
- `src/app/(account)/admin/writing/reviews/[reviewId]/page.tsx` — AI Draft Feedback panel
- mock updates in `writing-review.test.tsx`, `writing-rubric.test.tsx`

### Docs
- `docs/WRITING_REVIEW_WORKFLOW.md` — M5.3 section

## Tests added/updated

- *(new)* `backend/tests/test_writing_feedback_draft.py` — 16 tests: structured generation, persists draft, **does not create official feedback**, **does not publish**, works with rubric assigned, audited, student/parent/anon blocked, admin list, discard status, accept-creates-official-feedback, accept-marks-accepted, **accept does not publish**, cannot-generate-after-publish, **draft not exposed to student after publish**
- *(new)* `frontend/src/__tests__/writing-ai-draft.test.tsx` — 4 tests: panel + disclaimer, generate renders sections, copy-to-feedback (client-side, no save/publish), discard
- *(updated)* two existing frontend test mocks for the new mount-time `listAIDrafts` call

## Constraint compliance

- Never modifies rubric scores — no write path to `writing_review_scores` (verified by `test_generate_works_with_rubric_assigned` + accept tests)
- Never publishes — `test_generate_does_not_publish_review`, `test_accept_does_not_publish_review`
- Never auto-overwrites official feedback — generation creates 0 feedback rows (`test_generate_does_not_create_official_feedback`); copy is an explicit human action
- Admin/reviewer-only — no student/parent route; `test_student/parent_cannot_*`
- No student PII to providers — `FeedbackParams` carries only task + submission text + rubric dimension labels
- M5.4 scoring assistance not implemented (documented as out-of-scope)

## Remaining limitations

- "Copy to Official Feedback" in the UI is a client-side copy into the editable textarea; the reviewer still edits and explicitly saves/publishes. The `accept` endpoint offers the same as an auditable server-side action.
- Draft status transitions (e.g. cannot accept a discarded draft) are enforced at the service layer, not by a DB trigger — consistent with the M5.2 score-immutability approach.
- `draft_feedback_json` stores the structured draft as `sa.JSON` (not snapshotting the rubric text), consistent with the existing no-snapshot limitation noted for M5.2.

Nothing is committed — all changes are staged in the working tree for review.
