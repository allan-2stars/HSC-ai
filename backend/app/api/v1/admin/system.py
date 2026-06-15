from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin_profile
from app.models.user import AdminProfile
from app.services import system_service

router = APIRouter(prefix="/admin/system", tags=["admin-system"])


@router.get("")
async def admin_system_dashboard(
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await system_service.get_admin_system_dashboard(db)
