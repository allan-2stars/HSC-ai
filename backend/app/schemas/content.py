from pydantic import BaseModel, field_validator


class SubjectCreateRequest(BaseModel):
    code: str
    name: str

    @field_validator("code")
    @classmethod
    def code_nonempty(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("code cannot be empty")
        return v

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class SubjectUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class SubjectResponse(BaseModel):
    id: str
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class ExamTypeCreateRequest(BaseModel):
    code: str
    name: str

    @field_validator("code")
    @classmethod
    def code_nonempty(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("code cannot be empty")
        return v

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class ExamTypeUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class ExamTypeResponse(BaseModel):
    id: str
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class TopicCreateRequest(BaseModel):
    subject_id: str
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class TopicUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class TopicResponse(BaseModel):
    id: str
    subject_id: str
    name: str
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class SkillTagCreateRequest(BaseModel):
    name: str
    subject_id: str | None = None

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class SkillTagUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class SkillTagResponse(BaseModel):
    id: str
    name: str
    subject_id: str | None
    is_active: bool

    model_config = {"from_attributes": True}
