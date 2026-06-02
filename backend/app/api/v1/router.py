from fastapi import APIRouter

from app.api.v1 import auth, parents, students
from app.api.v1.admin import content as admin_content

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(parents.router)
router.include_router(students.router)
router.include_router(admin_content.router)
