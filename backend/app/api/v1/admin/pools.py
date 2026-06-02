from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_admin_profile
from app.models.user import AdminProfile, User
from app.schemas.question import (
    PoolCreateRequest,
    PoolMemberAddRequest,
    PoolResponse,
    QuestionResponse,
)
from app.services import question_service

router = APIRouter(prefix="/admin", tags=["admin-pools"])


@router.post("/pools", response_model=PoolResponse, status_code=201)
async def create_pool(
    body: PoolCreateRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.create_pool(
        name=body.name,
        created_by_admin_id=admin_profile.id,
        db=db,
        description=body.description,
        subject_id=body.subject_id,
        exam_type_id=body.exam_type_id,
        year_level=body.year_level,
    )


@router.get("/pools", response_model=list[PoolResponse])
async def list_pools(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_pools(db=db)


@router.get("/pools/{pool_id}", response_model=PoolResponse)
async def get_pool(
    pool_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.get_pool(pool_id=pool_id, db=db)


@router.post("/pools/{pool_id}/members", status_code=201)
async def add_pool_member(
    pool_id: str,
    body: PoolMemberAddRequest,
    admin_profile: AdminProfile = Depends(get_current_admin_profile),
    db: AsyncSession = Depends(get_db),
):
    await question_service.add_to_pool(
        pool_id=pool_id,
        question_id=body.question_id,
        admin_id=admin_profile.id,
        db=db,
    )
    return {"pool_id": pool_id, "question_id": body.question_id}


@router.get("/pools/{pool_id}/members", response_model=list[QuestionResponse])
async def list_pool_members(
    pool_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_pool_members(pool_id=pool_id, db=db)


@router.delete("/pools/{pool_id}/members/{question_id}", status_code=204)
async def remove_pool_member(
    pool_id: str,
    question_id: str,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await question_service.remove_from_pool(
        pool_id=pool_id, question_id=question_id, db=db
    )
