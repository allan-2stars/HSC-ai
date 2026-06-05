"""OCR processing service. Uses PyMuPDF for PDFs, PaddleOCR for images.
Structured question detection via regex."""
import io
import os
import re
import tempfile
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_job import OCRJob, OCRJobStatus, OCRPageResult
from app.models.question import (
    ContentOwnershipType,
    DifficultyLevel,
    Question,
    QuestionStatus,
    QuestionType,
    QuestionVersion,
    SourceType,
)

# ── PaddleOCR singleton ──────────────────────────────────────────────────────

_paddle_ocr = None


def _get_paddle_ocr():
    """Lazy-load PaddleOCR. Falls back to None if not installed."""
    global _paddle_ocr
    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
            _paddle_ocr = PaddleOCR(lang="en", use_angle_cls=False, show_log=False)
        except ImportError:
            _paddle_ocr = False  # Sentinel — don't retry
    return _paddle_ocr if _paddle_ocr is not False else None


# ── Text extraction ──────────────────────────────────────────────────────────


async def extract_text(file: UploadFile, max_pages: int = 50) -> tuple[str, list[dict]]:
    """Extract raw text from uploaded file. Returns (full_text, [{page_number, extracted_text, confidence}])."""
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        return _extract_pdf(content, max_pages)
    elif filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return _extract_image(content, filename)
    else:
        raise HTTPException(status_code=422, detail="Unsupported format. Use PDF, PNG, JPG, JPEG, or WEBP.")


def _extract_pdf(content: bytes, max_pages: int = 50) -> tuple[str, list[dict]]:
    """Extract text from PDF using PyMuPDF. Also runs PaddleOCR on image-only pages."""
    try:
        import fitz
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF support not installed (missing pymupdf/fitz)")

    doc = fitz.open(stream=content, filetype="pdf")
    pages = []
    full_text = []
    ocr = _get_paddle_ocr()

    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        text = page.get_text().strip()

        # If PyMuPDF found no text, try PaddleOCR on the page image
        if not text and ocr:
            pix = page.get_pixmap(dpi=200)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                pix.save(tmp.name)
                try:
                    result = ocr.ocr(tmp.name)
                    if result and result[0]:
                        text = " ".join(word[1][0] for word in result[0])
                finally:
                    os.unlink(tmp.name)

        full_text.append(text)
        pages.append({
            "page_number": i + 1,
            "extracted_text": text,
            "confidence": 0.8 if text else 0.0,
        })
    doc.close()
    return "\n\n".join(full_text), pages


def _extract_image(content: bytes, filename: str) -> tuple[str, list[dict]]:
    """Extract text from images using PaddleOCR."""
    ocr = _get_paddle_ocr()

    if ocr:
        with tempfile.NamedTemporaryFile(suffix="." + filename.split(".")[-1], delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            try:
                result = ocr.ocr(tmp.name)
                if result and result[0]:
                    text = " ".join(word[1][0] for word in result[0])
                    confidence = sum(word[1][1] for word in result[0]) / len(result[0]) if result[0] else 0.0
                else:
                    text = f"[No text detected in {filename}]"
                    confidence = 0.0
            except Exception:
                text = f"[OCR processing failed for {filename}]"
                confidence = 0.0
            finally:
                os.unlink(tmp.name)
        return text, [{"page_number": 1, "extracted_text": text, "confidence": round(confidence, 2)}]
    else:
        # Fallback: Pillow metadata only
        try:
            from PIL import Image
        except ImportError:
            raise HTTPException(status_code=500, detail="Image support not installed (missing Pillow)")

        img = Image.open(io.BytesIO(content))
        text = f"[Image: {filename}, size: {img.size[0]}x{img.size[1]}]"
        img.close()
        return text, [{"page_number": 1, "extracted_text": text, "confidence": 0.0}]


# ── Structured question detection ────────────────────────────────────────────

_QUESTION_START = re.compile(r"^(\d+)[\.\)]\s", re.MULTILINE)
_OPTION_LINE = re.compile(r"^([A-D])[\.\)]\s", re.MULTILINE)
_ANSWER_KEY = re.compile(r"(?:answer|answer\s*key|correct\s*answer)\s*[:=]?\s*([A-D])", re.IGNORECASE)
_EXPLANATION_START = re.compile(r"(?:explanation|why)\s*[:=]?", re.IGNORECASE)


def detect_questions(raw_text: str) -> list[dict]:
    """Detect structured MCQ questions from raw OCR text. Returns list of question dicts."""
    questions = []
    lines = raw_text.strip().split("\n")

    current = None
    buffer_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for question number start
        q_match = _QUESTION_START.match(stripped)
        if q_match and not _OPTION_LINE.match(stripped):
            # Save previous question
            if current and buffer_lines:
                current["options_before_completion"] = buffer_lines[:]
                questions.append(_finalize_question(current, buffer_lines[:]))
            current = {"question_number": int(q_match.group(1)), "stem_lines": [], "options": []}
            buffer_lines = [stripped]
            continue

        # Check for option line
        opt_match = _OPTION_LINE.match(stripped)
        if opt_match and current:
            current["options"].append({"label": opt_match.group(1), "text": stripped})
            buffer_lines.append(stripped)
            continue

        buffer_lines.append(stripped)

    # Finalize last question
    if current and buffer_lines:
        questions.append(_finalize_question(current, buffer_lines[:]))

    return questions


def _finalize_question(current: dict, all_lines: list[str]) -> dict:
    """Parse stem, options, answer key, and explanation from detected question."""
    full_text = " ".join(all_lines)
    stem = current.get("stem_lines", [])
    options = current.get("options", [])

    # Try to find answer key in the text
    answer_match = _ANSWER_KEY.search(full_text)
    detected_answer = answer_match.group(1) if answer_match else None

    # Try to find explanation
    expl_match = _EXPLANATION_START.search(full_text)
    explanation = full_text[expl_match.end():].strip() if expl_match else ""

    # Build MCQ options
    options_json = []
    for opt in options:
        options_json.append({
            "label": opt["label"],
            "text": opt["text"],
            "is_correct": detected_answer and opt["label"] == detected_answer,
            "explanation": "",
        })

    # If no options detected, create generic ones
    if not options_json:
        stem_text = " ".join(stem) if stem else full_text[:200]
        options_json = [
            {"label": "A", "text": "(Answer A)", "is_correct": True, "explanation": ""},
            {"label": "B", "text": "(Answer B)", "is_correct": False, "explanation": ""},
            {"label": "C", "text": "(Answer C)", "is_correct": False, "explanation": ""},
            {"label": "D", "text": "(Answer D)", "is_correct": False, "explanation": ""},
        ]

    return {
        "stem": " ".join(stem) if stem else full_text[:200],
        "correct_answer": detected_answer or "A",
        "explanation": explanation or "OCR extracted — requires admin review.",
        "options_json": options_json,
        "confidence": 0.5 if detected_answer else 0.3,
    }


# ── Job management ───────────────────────────────────────────────────────────

async def create_ocr_job(admin_id: str, filename: str, file_format: str, db: AsyncSession) -> OCRJob:
    job = OCRJob(
        filename=filename,
        file_format=file_format,
        uploaded_by=admin_id,
        status=OCRJobStatus.pending,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def process_ocr_job(job_id: str, db: AsyncSession) -> OCRJob:
    """Process an OCR job — extract text, detect questions, store page results."""
    job = await _get_job(job_id, db)
    if job.status != OCRJobStatus.pending:
        raise HTTPException(status_code=409, detail="Job is not in pending state")

    job.status = OCRJobStatus.processing
    job.started_at = datetime.now(tz=timezone.utc)
    await db.commit()

    try:
        raw_text = job.ocr_results_json.get("raw_text", "") if job.ocr_results_json else ""
        pages = job.ocr_results_json.get("pages", []) if job.ocr_results_json else []

        if not pages:
            raise HTTPException(status_code=422, detail="No OCR data to process")

        # Detect structured questions
        questions = detect_questions(raw_text)

        # Store page results
        for page in pages:
            page_questions = [q for q in questions if q["confidence"] > 0]
            pr = OCRPageResult(
                ocr_job_id=job.id,
                page_number=page["page_number"],
                extracted_text=page["extracted_text"],
                confidence=page["confidence"],
                structured_questions_json=page_questions if page["page_number"] == 1 else None,
            )
            db.add(pr)

        # Store all detected questions on the job
        job.ocr_results_json = job.ocr_results_json or {}
        job.ocr_results_json["questions"] = questions
        job.questions_detected = len(questions)
        job.status = OCRJobStatus.completed
        job.completed_at = datetime.now(tz=timezone.utc)
        await db.commit()

    except Exception as e:
        job.status = OCRJobStatus.failed
        job.error_message = str(e)
        job.completed_at = datetime.now(tz=timezone.utc)
        await db.commit()

    await db.refresh(job)
    return job


async def create_drafts_from_ocr(
    job_id: str, admin_id: str, db: AsyncSession,
    subject_id: str = "", exam_type_id: str = "",
) -> OCRJob:
    """Create draft questions from detected OCR questions. Requires valid subject_id and exam_type_id."""
    if not subject_id or not exam_type_id:
        raise HTTPException(status_code=422, detail="subject_id and exam_type_id are required")

    job = await _get_job(job_id, db)
    if job.status != OCRJobStatus.completed:
        raise HTTPException(status_code=409, detail="Job is not in completed state")

    questions_data = (job.ocr_results_json or {}).get("questions", [])
    if not questions_data:
        raise HTTPException(status_code=422, detail="No questions detected in OCR job")

    created = 0
    for q_data in questions_data:
        try:
            q = Question(
                subject_id=subject_id,
                exam_type_id=exam_type_id,
                year_level=5,
                difficulty=DifficultyLevel.medium,
                question_type=QuestionType.mcq,
                status=QuestionStatus.draft,
                source_type=SourceType.ocr,
                content_ownership=ContentOwnershipType.internal_draft,
                created_by_admin_id=admin_id,
                current_version_id=None,
            )
            db.add(q)
            await db.flush()

            v = QuestionVersion(
                question_id=q.id,
                version_number=1,
                stem=q_data["stem"],
                correct_answer=q_data.get("correct_answer", "A"),
                full_explanation=q_data.get("explanation", "OCR extracted — requires admin review."),
                marks=1,
                options_json=q_data.get("options_json"),
                created_by_admin_id=admin_id,
                created_at=datetime.now(tz=timezone.utc),
                metadata_json={"ocr_job_id": job_id, "ocr_confidence": q_data.get("confidence", 0.5)},
            )
            db.add(v)
            await db.flush()
            q.current_version_id = v.id
            created += 1

        except Exception:
            continue

    job.questions_created = created
    await db.commit()
    await db.refresh(job)
    return job


async def list_ocr_jobs(db: AsyncSession) -> list[OCRJob]:
    result = await db.execute(select(OCRJob).order_by(OCRJob.created_at.desc()).limit(50))
    return list(result.scalars().all())


async def get_ocr_job(job_id: str, db: AsyncSession) -> OCRJob:
    return await _get_job(job_id, db)


async def _get_job(job_id: str, db: AsyncSession) -> OCRJob:
    result = await db.execute(select(OCRJob).where(OCRJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="OCR job not found")
    return job
