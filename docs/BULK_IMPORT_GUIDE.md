# Bulk Content Import Guide

## 1. Supported Formats

| Format | Extension | Max Rows | Notes |
|---|---|---|---|
| CSV | `.csv` | 5000 | UTF-8 encoding required |
| Excel | `.xlsx` | 5000 | OpenPyXL parser |
| JSON | `.json` | 5000 | Array or `{ questions: [...] }` structure |

## 2. Download Templates

Templates with sample data are available from the import page:

```
GET /api/v1/admin/content/import/templates/csv
GET /api/v1/admin/content/import/templates/xlsx
GET /api/v1/admin/content/import/templates/json
```

Or visit `/admin/content/import` and click the template buttons.

## 3. Column Reference

| Column | Required | Description |
|---|---|---|
| `question_text` | **Yes** | The question stem/prompt |
| `answer` | **Yes** | Correct answer (A/B/C/D for MCQ) |
| `subject` | **Yes** | Subject code or name (e.g., "Mathematics") |
| `exam_type` | **Yes** | Exam type code or name (e.g., "OC") |
| `explanation` | No | Full explanation of the correct answer |
| `difficulty` | No | `easy`, `medium`, or `hard` (default: `medium`) |
| `topic` | No | Topic name within the subject |
| `skill` | No | Skill tag name within the subject |
| `curriculum_outcome` | No | Outcome code (e.g., `OC-MATH-FRACTIONS`) |
| `source_type` | No | `manual`, `ai`, `ocr`, `imported` (default: `imported`) |

Column names are case-insensitive and spaces/hyphens are normalized to underscores.
Valid alternatives: `Question Text`, `QUESTION_TEXT`, `question-text` all become `question_text`.

## 4. Validation Rules

Before import, all rows are validated:

1. **Required fields**: `question_text`, `answer`, `subject`, `exam_type` must be present and non-empty
2. **Subject lookup**: Subject must match an existing `code` or `name` in the database
3. **Exam type lookup**: Exam type must match an existing `code` or `name`
4. **Difficulty**: Must be `easy`, `medium`, or `hard` if provided
5. **Source type**: Must be `manual`, `ai`, `ocr`, or `imported` if provided
6. **Topic/Skill**: Optional — looked up by name within the subject
7. **Outcome**: Optional — looked up by exact code match

Rows that fail validation are shown with specific error messages in the preview.

## 5. Duplicate Detection

A row is considered a duplicate if the same `(question_text, subject_id, exam_type_id)` combination already exists in the database.

By default, duplicates are skipped. Uncheck "Skip duplicate questions" in the UI to import them anyway.

## 6. Example Imports

### CSV Example

```csv
question_text,answer,difficulty,subject,exam_type,explanation,topic,skill,curriculum_outcome,source_type
"What is 2 + 2?",A,easy,Mathematics,OC,"2 + 2 = 4",Number & Algebra,Addition/Subtraction,OC-MATH-NUM,imported
"What is 8 × 7?",C,medium,Mathematics,OC,"8 × 7 = 56",Number & Algebra,Multiplication/Division,OC-MATH-NUM,imported
```

### JSON Example

```json
{
  "questions": [
    {
      "question_text": "What is the value of π to 2 decimal places?",
      "answer": "A",
      "difficulty": "medium",
      "subject": "Mathematics",
      "exam_type": "OC",
      "topic": "Measurement & Geometry",
      "explanation": "π ≈ 3.14"
    }
  ]
}
```

## 7. Import Workflow

```
1. Upload CSV/XLSX/JSON
        ↓
2. Preview — review valid/invalid/duplicate counts
        ↓
3. Confirm Import
        ↓
4. Questions created as DRAFT (source_type = imported)
        ↓
5. Curriculum outcome mappings created automatically
        ↓
6. Questions appear in Content Review Queue
        ↓
7. Admin reviews → approves → publishes through existing workflow
```

## 8. After Import

- All imported questions have `status = "draft"` and `source_type = "imported"`
- They appear in the **Content Review** queue (`/admin/content/review`) filtered by `source_type = imported`
- They do NOT appear in curriculum coverage or exam instances until published
- An `ImportJob` record is created for audit

## 9. Import Job Audit

Every import creates an `ImportJob` record tracking:

| Field | Description |
|---|---|
| `id` | UUID |
| `filename` | Original filename |
| `format` | csv, xlsx, or json |
| `uploaded_by` | Admin who initiated the import |
| `status` | pending → processing → completed / failed |
| `imported_count` | Questions successfully created |
| `skipped_count` | Rows skipped |
| `failed_count` | Rows that failed during insertion |
| `duplicate_count` | Duplicates detected |
| `mapping_count` | Outcome mappings created |
| `started_at` | When import began |
| `completed_at` | When import finished |

View jobs: `GET /api/v1/admin/content/import/jobs`

## 10. Best Practices

1. **Start small**: Test with 5–10 questions before uploading thousands
2. **Use templates**: Download the template for your format to ensure correct column names
3. **Check preview**: Always review the preview before confirming import
4. **Map outcomes**: Include `curriculum_outcome` codes for automatic curriculum alignment
5. **Review after import**: All imports go through the Content Review queue before publication
6. **Use source_type**: Set source_type to track content origin (manual/ocr/ai/imported)
