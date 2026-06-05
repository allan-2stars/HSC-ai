from fastapi import APIRouter

from app.api.v1 import analytics, assignments, auth, curriculum, exams, parents, students
from app.api.v1.admin import ai_generate as admin_ai_generate
from app.api.v1.admin import content as admin_content
from app.api.v1.admin import content_import as admin_content_import
from app.api.v1.admin import content_ocr as admin_content_ocr
from app.api.v1.admin import content_review as admin_content_review
from app.api.v1.admin import exams as admin_exams
from app.api.v1.admin import pools as admin_pools
from app.api.v1.admin import questions as admin_questions

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(parents.router)
router.include_router(students.router)
router.include_router(admin_content.router)
router.include_router(admin_content_review.router)
router.include_router(admin_content_ocr.router)
router.include_router(admin_content_import.router)
router.include_router(admin_ai_generate.router)
router.include_router(admin_questions.router)
router.include_router(admin_pools.router)
router.include_router(admin_exams.router)
router.include_router(exams.router)
router.include_router(analytics.router)
router.include_router(assignments.router)
router.include_router(curriculum.router)
