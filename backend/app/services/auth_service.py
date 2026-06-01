from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import (
    ParentProfile,
    RefreshToken,
    User,
    UserRole,
)
from app.core.config import settings
from app.services.audit_service import log_action


async def register_parent(
    email: str,
    password: str,
    display_name: str,
    db: AsyncSession,
) -> User:
    existing = await db.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        role=UserRole.parent,
    )
    db.add(user)
    await db.flush()

    profile = ParentProfile(user_id=user.id, display_name=display_name)
    db.add(profile)

    await log_action(
        db,
        action="parent.registered",
        actor_user_id=user.id,
        actor_role=UserRole.parent.value,
        target_type="user",
        target_id=user.id,
    )

    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    return user


async def issue_tokens(user: User, db: AsyncSession) -> tuple[str, str]:
    """Returns (access_token, refresh_token_raw)."""
    access_token = create_access_token(sub=user.id, role=user.role.value)

    raw_token = generate_refresh_token()
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        created_at=datetime.now(timezone.utc),
    )
    db.add(token_record)

    await log_action(
        db,
        action="user.login",
        actor_user_id=user.id,
        actor_role=user.role.value,
        target_type="user",
        target_id=user.id,
    )

    await db.commit()
    return access_token, raw_token


async def refresh_tokens(raw_token: str, db: AsyncSession) -> tuple[str, str]:
    """Validates and rotates a refresh token. Returns (new_access_token, new_raw_token)."""
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.revoked_at.is_(None))
    )
    record = result.scalar_one_or_none()

    if not record or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        )

    # Revoke old token (rotation)
    record.revoked_at = datetime.now(timezone.utc)
    await db.flush()

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one()

    new_access = create_access_token(sub=user.id, role=user.role.value)
    new_raw = generate_refresh_token()
    new_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_raw),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_record)
    await db.commit()
    return new_access, new_raw


async def revoke_refresh_token(raw_token: str, db: AsyncSession) -> None:
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.revoked_at.is_(None))
    )
    record = result.scalar_one_or_none()
    if record:
        record.revoked_at = datetime.now(timezone.utc)
        await db.commit()
