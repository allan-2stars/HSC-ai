# OCR Import Pipeline

## 1. Purpose

The OCR import pipeline helps administrators convert PDFs, scanned exams, screenshots, and photos into structured question bank content.

OCR is a content-production tool only. It does not auto-publish content.

## 2. Supported Inputs

- PDF
- PNG
- JPG/JPEG
- WEBP

Sources may include:

- Scanned exam papers
- Phone photos
- Answer sheets
- Explanation sheets

## 3. Pipeline

```text
Admin Upload
        ↓
Raw Source Storage
        ↓
Native PDF Text Extraction if available
        ↓
OCR if needed
        ↓
AI Structure Extraction
        ↓
Review Queue
        ↓
Admin Edit / Approve / Reject
        ↓
Question Bank
```

## 4. Processing Rules

For PDFs:

- Try native text extraction first.
- If text is missing or poor quality, run OCR page by page.

For images/photos:

- Run preprocessing where practical:
  - rotation correction
  - deskew
  - contrast enhancement
  - crop detection

## 5. AI Structure Extraction

AI converts OCR text into draft structured objects:

- Exam title
- Section
- Question number
- Question stem
- Answer options
- Correct answer
- Explanation
- Marks
- Subject
- Exam type
- Year level
- Topic tags
- Difficulty estimate

## 6. Review Queue

Every OCR-generated question enters review.

Statuses:

- uploaded
- ocr_processing
- extraction_processing
- needs_review
- approved
- rejected
- published

## 7. Admin Review Screen

Admin should see:

- Original page image/PDF preview
- OCR text
- Extracted structured question
- Editable fields
- Confidence values
- Approve/reject controls

## 8. Traceability

Each generated question should store:

- source_file_id
- source_page_number
- source_region if available
- ocr_confidence
- extraction_confidence
- reviewed_by
- reviewed_at

## 9. Recommended Technology

MVP:

- PyMuPDF for PDF text extraction
- PaddleOCR or Tesseract for OCR
- LLM structured JSON extraction
- DB-backed job statuses

Future:

- Google Document AI
- Azure Document Intelligence
- More advanced layout detection

## 10. Non-Goals for MVP

- No automatic publishing.
- No handwriting recognition guarantee.
- No perfect diagram extraction.
- No automatic copyright/legal validation.
