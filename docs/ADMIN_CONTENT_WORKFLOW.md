# Admin Content Workflow

## 1. Purpose

Administrators control all question creation and publishing. Students and parents cannot create public content.

## 2. Content Sources

Questions can originate from:

- Manual entry
- OCR import
- AI generation

## 3. Unified Lifecycle

All content follows the same lifecycle regardless of source:

```text
Draft
  ↓
Review (admin mandatory for OCR and AI content)
  ↓
Approved
  ↓
Published
  ↓
Archived
```

Rejected content remains stored for audit unless deleted by admin policy.

## 4. Content Ownership Classification Requirement

Every question must carry a content ownership classification before it can be approved or published.

| Classification | Publishing Allowed |
|---|---|
| `original` | Yes |
| `licensed` | Yes |
| `public_domain` | Yes |
| `approved_internal` | Yes |
| `user_provided_with_rights` | Yes (with caution) |
| `internal_draft` | No |
| `restricted_reference_only` | No |

The system must block publishing for `internal_draft` and `restricted_reference_only` questions, regardless of review status.

Admins must review copyright status before assigning a publishable classification. Assigning a false classification creates legal liability.

## 5. Manual Entry

Admin creates:

- Question stem
- Options (for MCQ)
- Correct answer
- Full explanation
- Subject
- Exam type
- Topic
- Difficulty
- Marks
- Content ownership classification (required — set to `original` for admin-written questions)

## 6. OCR Import

OCR imported content enters review queue automatically with ownership defaulting to `internal_draft`.

During review, admin must:

- Compare source page, OCR text, and structured question
- Confirm or edit question content
- Assign content ownership classification based on confirmed copyright status
- Add a copyright note if the content is licensed or restricted

Admin cannot approve OCR content without assigning an ownership classification.

## 7. AI Generation

Admin can request AI-generated draft questions.

Example:

- 20 Year 5 fraction questions
- Medium difficulty
- Multiple choice
- Full explanation

AI-generated content:

- Enters the review queue as `draft` with ownership defaulting to `original` (since it was AI-generated under admin direction using the platform)
- Must be reviewed before publishing
- Can never be auto-published
- Admin may edit content during review

The mandatory workflow for all AI-generated content:

```text
Draft (AI generated)
  ↓
Review (admin mandatory — no exceptions)
  ↓
Approved
  ↓
Published
```

## 8. Question Versioning

Questions support versions.

When an admin changes published content, create a new version rather than mutating historical attempt references.

Attempt answers reference the question version used at attempt time. This preserves historical accuracy.

## 9. Writing Prompts

Writing prompts for the Selective School writing component follow the same lifecycle as questions.

Additional fields required on approval:

- Prompt type: narrative | persuasive | informative | imaginative
- Word limit (if applicable)
- Time limit in seconds
- Marks
- Content ownership classification

Writing prompts must be original content or explicitly licensed. They must not reproduce copyrighted writing prompts from official exam papers without a licence.

## 10. Exam Builder

Admins can build:

- Fixed exams (specific questions in fixed order)
- Dynamic exams (drawn from question pools by criteria)

V1 should prioritize fixed exams for predictable OC/Selective practice.

Writing exams require:

- At least one writing prompt
- A writing section with a defined time limit

## 11. Bulk Operations

Admins should be able to perform bulk operations on the review queue:

- Bulk approve (questions that clearly meet quality standards)
- Bulk reject with a shared reason
- Bulk assign ownership classification

Bulk approval must still require review of each question; it is a UX shortcut, not a bypass of the review requirement.

## 12. Content Quality Analytics

Admin should eventually see:

- Difficulty distribution across the question bank
- Topic coverage gaps
- Questions with high wrong-answer rate (potential ambiguity or error)
- Questions frequently flagged by users
- Questions pending ownership review
