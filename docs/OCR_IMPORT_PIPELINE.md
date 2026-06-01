# OCR Import Pipeline

## 1. Purpose

The OCR import pipeline helps administrators convert PDFs, scanned exams, screenshots, and photos into structured question bank content.

OCR is a content ingestion tool only. It does not grant publishing rights and does not auto-publish content.

OCR-imported content always enters review before it can be published. Publishing is further restricted by the content ownership classification assigned during review.

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
Native PDF Text Extraction (if available)
        ↓
OCR (if needed)
        ↓
AI Structure Extraction
        ↓
Review Queue (status: needs_review)
        ↓
Admin Ownership Review
        ↓
  Copyright-safe? → Assign publishable ownership classification
  Copyright unclear? → Classify as internal_draft or restricted_reference_only
        ↓
Admin Edit / Approve / Reject
        ↓
Question Bank (published only if ownership classification permits)
```

## 4. Processing Rules

For PDFs:

- Try native text extraction first.
- If text is missing or poor quality, run OCR page by page.

For images/photos:

- Run preprocessing where practical:
  - Rotation correction
  - Deskew
  - Contrast enhancement
  - Crop detection

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

AI structure extraction is a drafting aid. All extracted content requires admin review before it can be approved or published.

## 6. Content Ownership Classification

Every OCR-imported question must be assigned a content ownership classification during admin review.

**OCR-imported content defaults to `internal_draft` upon ingestion.**

The admin must determine the correct classification before approving for publishing:

| Classification | When to Apply | Publishing Allowed |
|---|---|---|
| `original` | Admin rewrote or created content from scratch using OCR as a reference only | Yes |
| `licensed` | Source material is covered by a confirmed platform licence | Yes |
| `public_domain` | Source confirmed as public domain | Yes |
| `approved_internal` | Internal draft reviewed and cleared for publishing | Yes |
| `internal_draft` | Copyright status not yet confirmed | No |
| `restricted_reference_only` | Source is copyright-protected; not cleared for publishing | No |

### Copyright Warning

Ingesting a copyrighted document does not grant publishing rights. The following content types are copyright-protected and cannot be published without a licence:

- Official NSW OC test papers
- Official NSW Selective High School test papers
- Third-party question banks or workbooks
- Copyrighted images, diagrams, or charts

If an admin is uncertain about a source's copyright status, they must classify it as `internal_draft` or `restricted_reference_only` and seek legal review before assigning a publishable classification.

Assigning a publishable classification to content that is not genuinely owned or licensed is a misuse of the platform and creates legal liability.

## 7. Review Queue

Every OCR-generated question enters review.

Statuses:

- `uploaded` — source file received
- `ocr_processing` — OCR job running
- `extraction_processing` — AI structure extraction running
- `needs_review` — awaiting admin review and ownership classification
- `in_review` — claimed by an admin (prevents concurrent review conflicts)
- `approved` — reviewed, ownership assigned, approved for question bank
- `rejected` — rejected with reason
- `published` — promoted to published question bank

## 8. Admin Review Screen

Admin must see:

- Original page image or PDF preview
- OCR extracted text
- Extracted structured question (editable)
- Confidence values (OCR confidence, extraction confidence)
- Content ownership classification selector (required before approval)
- Copyright note field (for attribution or restriction reason)
- Approve/reject controls

The approval action must be blocked if the content ownership classification is `internal_draft` or `restricted_reference_only`.

## 9. Traceability

Each generated question must store:

- `source_file_id`
- `source_page_number`
- `source_region` (if available)
- `ocr_confidence`
- `extraction_confidence`
- `content_ownership` (assigned by admin at review)
- `copyright_note` (optional)
- `reviewed_by`
- `reviewed_at`

## 10. Recommended Technology

MVP:

- PyMuPDF for native PDF text extraction
- PaddleOCR or Tesseract for OCR on images/scanned pages
- LLM structured JSON extraction for question structuring
- DB-backed job statuses

For maths-heavy content:

- Consider Pix2Text as a supplementary OCR step to handle mathematical notation (fractions, equations) that standard OCR misses.

Future:

- Google Document AI
- Azure Document Intelligence
- More advanced layout and diagram detection

## 11. Non-Goals for MVP

- No automatic publishing of OCR content.
- No automatic copyright determination.
- No handwriting recognition guarantee.
- No perfect diagram extraction.
- No auto-assignment of ownership classifications.
