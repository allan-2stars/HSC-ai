import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(sub: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": sub, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises JWTError on failure."""
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()
