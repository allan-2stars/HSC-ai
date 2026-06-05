# OCR Import Pipeline

## 1. Purpose

The OCR Import Pipeline allows administrators to upload PDF and image files, extract question content via OCR, review the extracted content, and convert it into draft questions that feed the existing content review workflow.

All OCR-imported questions default to `source_type = ocr` and `content_ownership = internal_draft`. They cannot be published until they pass through the standard review process (draft → review → approved → published).

## 2. Architecture

```
Upload PDF/Image
     │
     ▼
┌─────────────┐
│  extract_text│  (PyMuPDF for PDF, Pillow for images)
└──────┬──────┘
       │ raw text + pages
       ▼
┌─────────────┐
│detect_questions│ (regex-based MCQ structure detection)
└──────┬──────┘
       │ structured questions
       ▼
┌─────────────┐
│ Admin Review │  (UI: /admin/content/ocr)
│ - view raw   │
│ - view detected Qs │
│ - assign subject/exam │
└──────┬──────┘
       │ confirm
       ▼
┌──────────────┐
│ Create Drafts │  Question + QuestionVersion created
│ status=draft  │  source_type=ocr
│ content_ownership=internal_draft │
└──────┬──────┘
       │
       ▼
┌──────────────┐
│ Review Queue  │  /admin/content/review
│ → approve    │
│ → publish    │
└──────────────┘
```

## 3. Supported Formats

| Format | Extensions | Engine | Confidence |
|---|---|---|---|
| PDF | `.pdf` | PyMuPDF (fitz) | ~0.8 (text extraction) |
| PNG | `.png` | Pillow metadata | 0.0 (image only — real OCR requires PaddleOCR) |
| JPEG | `.jpg`, `.jpeg` | Pillow metadata | 0.0 |
| WEBP | `.webp` | Pillow metadata | 0.0 |

## 4. Structured Question Detection

The pipeline uses regex-based detection to identify:

- Question numbers (`1.`, `2)`, etc.)
- Option lines (`A.`, `B)`, `C.`, `D.`)
- Answer keys (`Answer: A`, `Correct Answer: B`)
- Explanation markers (`Explanation:`, `Why:`)

Detection is intentionally basic — admin review is mandatory. A confidence score of 0.5 is assigned to questions where an answer key was successfully matched.

## 5. Review Requirements

Every OCR-imported question must:

1. Have `subject_id` and `exam_type_id` assigned before draft creation
2. Pass through the Content Review queue
3. Be approved and published through the standard workflow

OCR-imported questions use `content_ownership = internal_draft`, which blocks automatic publishing. The admin must upgrade the ownership classification during review.

## 6. Pluggable OCR Engine

The `extract_text()` function in `ocr_service.py` is designed to be swapped for a real OCR engine:

```python
# Current: PyMuPDF for PDF, Pillow metadata for images
# Future: PaddleOCR / Tesseract / Pix2Text
async def extract_text(file: UploadFile) -> tuple[str, list[dict]]:
    ...
```

To integrate PaddleOCR:
1. Install `paddlepaddle` and `paddleocr`
2. Replace `_extract_image()` with PaddleOCR-based text extraction
3. Confidence scores will reflect actual OCR quality

## 7. APIs

| Method | Path | Purpose |
|---|---|---|
| POST | `/admin/content/ocr/upload` | Upload file, extract text, detect questions |
| POST | `/admin/content/ocr/{job_id}/process` | Re-process text extraction on existing job |
| POST | `/admin/content/ocr/{job_id}/create-drafts` | Create draft questions from OCR results |
| GET | `/admin/content/ocr/jobs` | List OCR jobs |
| GET | `/admin/content/ocr/jobs/{job_id}` | Get job detail with extracted text and questions |

## 8. Limitations

1. **Image OCR is placeholder**: PNG/JPG/WEBP files currently extract metadata only. Full image OCR requires PaddleOCR (see above).
2. **No font/format awareness**: The regex detector works best with simple numbered-question formats. Complex layouts may produce incomplete results.
3. **Answer detection is basic**: Only exact matches of "Answer: X" or "Correct Answer: X" are detected.
4. **No multi-column layout support**: Text is extracted linearly. Multi-column exam papers may interleave questions.
5. **Confidence scores are estimates**: They reflect detection success, not true OCR confidence.
6. **No batch processing**: Files are processed one at a time, synchronously.
7. **No image preview**: The review screen shows extracted text only, not the original image.

## 9. Future Enhancements

- PaddleOCR integration for full image/PDF OCR
- Pix2Text for maths-heavy content extraction
- Table detection for structured answer keys
- Confidence-based filtering (skip questions below threshold)
- Original file display alongside extracted text in review UI
- Batch upload support (multiple files at once)
- Background processing for large files
