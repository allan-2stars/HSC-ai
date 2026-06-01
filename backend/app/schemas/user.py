from datetime import datetime

from pydantic import BaseModel, field_validator


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StudentCreateRequest(BaseModel):
    display_name: str
    year_level: int | None = None
    initial_password: str | None = None

    @field_validator("display_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("display_name cannot be empty")
        return v.strip()

    @field_validator("year_level")
    @classmethod
    def valid_year(cls, v: int | None) -> int | None:
        if v is not None and v not in range(4, 7):
            raise ValueError("year_level must be 4, 5, or 6")
        return v


class StudentUpdateRequest(BaseModel):
    display_name: str | None = None
    year_level: int | None = None

    @field_validator("year_level")
    @classmethod
    def valid_year(cls, v: int | None) -> int | None:
        if v is not None and v not in range(4, 7):
            raise ValueError("year_level must be 4, 5, or 6")
        return v


class StudentResponse(BaseModel):
    id: str
    display_name: str
    year_level: int | None
    first_login_completed: bool
    # Returned only at creation — shows temp credentials for parent to relay to child
    login_email: str | None = None
    temp_password: str | None = None

    model_config = {"from_attributes": True}


class FirstLoginRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
