from datetime import datetime

from pydantic import BaseModel

from app.models.assignment import AssignmentStatus


class AssignmentCreateRequest(BaseModel):
    exam_instance_id: str
    due_at: datetime | None = None


class AssignmentUpdateRequest(BaseModel):
    due_at: datetime | None = None
    status: AssignmentStatus | None = None


class AssignmentResponse(BaseModel):
    id: str
    student_id: str
    exam_instance_id: str
    assigned_by_parent_id: str
    title_snapshot: str
    due_at: datetime | None
    status: AssignmentStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssignmentListResponse(BaseModel):
    id: str
    student_id: str
    exam_instance_id: str
    title_snapshot: str
    due_at: datetime | None
    status: AssignmentStatus
    student_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignmentSummaryResponse(BaseModel):
    assigned: int
    started: int
    completed: int
    overdue: int
    cancelled: int
