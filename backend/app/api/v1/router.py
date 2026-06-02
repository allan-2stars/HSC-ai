from fastapi import APIRouter

from app.api.v1 import auth, parents, students
from app.api.v1.admin import content as admin_content
from app.api.v1.admin import questions as admin_questions

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(parents.router)
router.include_router(students.router)
router.include_router(admin_content.router)
router.include_router(admin_questions.router)
