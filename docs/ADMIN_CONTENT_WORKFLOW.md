# Admin Content Workflow

## 1. Purpose

Administrators control all question creation and publishing. Students and parents cannot create public content.

## 2. Content Sources

Questions can originate from:

- Manual entry
- OCR import
- AI generation

## 3. Unified Lifecycle

All content follows:

```text
Draft
  ↓
Review
  ↓
Approved
  ↓
Published
  ↓
Archived
```

Rejected content remains stored for audit/debugging unless deleted by admin policy.

## 4. Manual Entry

Admin creates:

- Question stem
- Options
- Correct answer
- Full explanation
- Subject
- Exam type
- Topic
- Difficulty
- Marks

## 5. OCR Import

OCR imported content enters review queue automatically.

Admin must compare:

- Source page
- OCR text
- Structured question

## 6. AI Generation

Admin can request AI-generated draft questions.

Example:

- 20 Year 5 fraction questions
- Medium difficulty
- Multiple choice
- Full explanation

Generated content must be reviewed before publishing.

## 7. Question Versioning

Questions should support versions.

When admin changes published content, create a new version rather than mutating historical attempt references.

Attempt answers should reference the question version used at attempt time.

## 8. Exam Builder

Admins can build:

- Fixed exams
- Dynamic exams from question pools

V1 should prioritize fixed exams for OC/Selective practice.

## 9. Content Quality Analytics

Admin should eventually see:

- Difficulty distribution
- Topic coverage
- Too many/too few questions by area
- Questions with high wrong rate
- Questions frequently flagged by users
