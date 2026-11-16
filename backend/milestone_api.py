"""Authenticated Milestone API for the current student team."""
from datetime import date, datetime
import re
from typing import Literal
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from backend.auth_api import ASCII_SPACE, AuthError, CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, error_response, require_origin, unauthenticated
from backend.auth_security import session_digest, valid_csrf
from backend.milestone_store import MilestoneError, milestone_transaction


def text(value, name=False):
    if value is None and not name:
        return None
    if not isinstance(value, str) or "\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError("MILESTONE_TEXT_INVALID")
    value = value.strip(ASCII_SPACE)
    if name and (not value or len(value) > 255):
        raise ValueError("MILESTONE_NAME_INVALID")
    return value if name else value or None


def due(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("MILESTONE_DATE_INVALID")
    return date.fromisoformat(value)


class CreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str
    description: str | None = None
    due_date: date
    _name = field_validator("name", mode="before")(lambda v: text(v, True))
    _description = field_validator("description", mode="before")(lambda v: text(v))
    _due = field_validator("due_date", mode="before")(due)


class UpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str | None = None
    description: str | None = None
    due_date: date | None = None
    _name = field_validator("name", mode="before")(lambda v: text(v, True))
    _description = field_validator("description", mode="before")(lambda v: text(v))
    _due = field_validator("due_date", mode="before")(due)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set:
            raise ValueError("MILESTONE_UPDATE_REQUIRED")
        return self


class Milestone(BaseModel):
    id: str
    project_id: str
    name: str
    description: str | None
    due_date: date
    status: Literal["not_started", "in_progress", "completed"]
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str | None
    completed_at: datetime | None


class MilestoneResponse(BaseModel):
    data: Milestone


class Listing(BaseModel):
    project_id: str
    can_manage: bool
    milestones: list[Milestone]


class ListResponse(BaseModel):
    data: Listing


ERRORS = {
    "TEAM_NOT_FOUND": (404, "คุณยังไม่มีทีม"), "PROJECT_NOT_FOUND": (404, "ทีมยังไม่มีโครงงาน"),
    "MILESTONE_NOT_FOUND": (404, "ไม่พบแผนงานที่คุณมีสิทธิ์เข้าถึง"),
    "MILESTONE_ACTION_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่จัดการแผนงานได้"),
    "MILESTONE_LOCKED": (409, "แผนงานถูกล็อกหลังมีคะแนนประเมินแล้ว"),
    "MILESTONE_NAME_CONFLICT": (409, "ชื่อแผนงานซ้ำในโครงงานนี้"),
    "MILESTONE_DUE_DATE_PAST": (422, "วันกำหนดส่งต้องไม่ก่อนวันนี้ตามเวลาไทย"),
    "TASK_DUE_DATE_CONFLICT": (409, "ต้องปรับวันกำหนดส่งของงานย่อยก่อนย่อวันแผนงาน"),
    "MILESTONE_HAS_TASKS": (409, "ลบแผนงานที่มีงานย่อยไม่ได้"),
}
router = APIRouter(tags=["milestones"], dependencies=[Depends(require_origin)])


def get_milestone_uow():
    return milestone_transaction


def path_id(value):
    if not re.fullmatch(r"[1-9][0-9]{0,18}", value) or int(value) > 9223372036854775807:
        raise AuthError(422, "VALIDATION_ERROR", "รหัสแผนงานไม่ถูกต้อง")
    return int(value)


def run(request, uow, operation, write=False):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    if digest is None:
        raise unauthenticated()
    try:
        with uow() as store:
            user = store.auth.active_user(digest)
            if user is None:
                raise unauthenticated()
            if write and not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
                raise AuthError(403, "CSRF_INVALID", "ไม่สามารถยืนยันคำขอได้")
            if user["role"] != "student":
                raise AuthError(403, "MILESTONE_ACCESS_FORBIDDEN", "หน้านี้สำหรับนักศึกษา")
            result = operation(store, user["id"])
    except MilestoneError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


@router.get("/api/v1/projects/me/milestones", response_model=ListResponse)
def listing(request: Request, uow=Depends(get_milestone_uow)):
    return run(request, uow, lambda s, a: ListResponse(data=s.listing(a)))


@router.post("/api/v1/projects/me/milestones", status_code=201, response_model=MilestoneResponse)
def create(payload: CreateInput, request: Request, uow=Depends(get_milestone_uow)):
    return run(request, uow, lambda s, a: MilestoneResponse(data=s.create(a, payload.name, payload.description, payload.due_date)), True)


@router.get("/api/v1/milestones/{milestone_id}", response_model=MilestoneResponse)
def detail(milestone_id: str, request: Request, uow=Depends(get_milestone_uow)):
    return run(request, uow, lambda s, a: MilestoneResponse(data=s.detail(a, path_id(milestone_id))))


@router.patch("/api/v1/milestones/{milestone_id}", response_model=MilestoneResponse)
def update(milestone_id: str, payload: UpdateInput, request: Request, uow=Depends(get_milestone_uow)):
    return run(request, uow, lambda s, a: MilestoneResponse(data=s.update(a, path_id(milestone_id), payload.model_dump(exclude_unset=True))), True)


@router.delete("/api/v1/milestones/{milestone_id}", status_code=204)
def delete(milestone_id: str, request: Request, uow=Depends(get_milestone_uow)):
    run(request, uow, lambda s, a: s.delete(a, path_id(milestone_id)), True)
    return Response(status_code=204)


async def milestone_validation_error_handler(request, exc):
    return error_response(422, "VALIDATION_ERROR", "กรุณาตรวจชื่อ คำอธิบาย และวันกำหนดส่งของแผนงาน")


async def milestone_storage_error_handler(request, exc):
    return error_response(500, "INTERNAL_ERROR", "ระบบแผนงานยังไม่พร้อมใช้งาน กรุณาตรวจรายการอีกครั้ง")
