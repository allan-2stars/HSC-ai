from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.user import FirstLoginRequest
from app.services import family_service

router = APIRouter(prefix="/students", tags=["students"])


@router.post("/first-login", status_code=204)
async def first_login(
    body: FirstLoginRequest,
    student: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Student sets their own password and marks first_login_completed.

    The student must already be authenticated (with the temp credentials set by the parent).
    After this call, first_login_completed = True.
    """
    await family_service.complete_first_login(
        student_user_id=student.id,
        new_password=body.new_password,
        db=db,
    )
