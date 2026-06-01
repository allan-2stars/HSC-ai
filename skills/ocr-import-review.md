# Skill: OCR Import Review

Use this skill when implementing OCR upload, extraction, or review workflows.

## Core Rule

OCR output must never auto-publish.

## Required Workflow

```text
Upload
  ↓
OCR Processing
  ↓
AI Structure Extraction
  ↓
Review Queue (status: needs_review, ownership: internal_draft)
  ↓
Admin Reviews Content AND Assigns Ownership Classification
  ↓
Admin Approves or Rejects
  ↓
Publish (only if ownership classification permits)
```

## Content Ownership Requirement

OCR-imported content defaults to `internal_draft`. The admin must assign a valid ownership classification before the question can be approved or published.

Publishing is blocked for `internal_draft` and `restricted_reference_only` classifications. The system must enforce this at the API level.

## Required Metadata

Each OCR-generated question must store:

- `source_file_id`
- `source_page_number`
- `ocr_confidence`
- `extraction_confidence`
- `content_ownership` (assigned by admin during review)
- `copyright_note` (optional, for attribution or restriction reason)
- `reviewed_by`
- `reviewed_at`

## Admin Review UI Requirements

Show:

- Source page image or PDF preview
- OCR extracted text
- Extracted structured question (editable)
- Confidence values (OCR confidence, extraction confidence)
- Content ownership classification selector (required before approval)
- Copyright note field
- Approve / Reject controls

The Approve button must be disabled if `content_ownership` is `internal_draft` or `restricted_reference_only`.

## Copyright Warning Display

The admin review screen must display a visible warning:

> "Ingesting a document does not grant publishing rights. Confirm copyright ownership before assigning a publishable classification."
