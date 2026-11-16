"""Current-team Task, status, assignee and history endpoints."""
from datetime import date, datetime
import re
from typing import Literal
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from backend.auth_api import AuthError, CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, error_response, require_origin, unauthenticated
from backend.auth_security import session_digest, valid_csrf
from backend.milestone_api import Milestone
from backend.milestone_store import MilestoneError
from backend.task_store import TaskError, task_transaction
from backend.task_validation import task_name, task_description, task_due_date, task_status


class CreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str
    description: str | None = None
    due_date: date | None = None
    _name = field_validator("name", mode="before")(task_name)
    _description = field_validator("description", mode="before")(task_description)
    _due = field_validator("due_date", mode="before")(task_due_date)


class UpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str | None = None
    description: str | None = None
    due_date: date | None = None
    _name = field_validator("name", mode="before")(task_name)
    _description = field_validator("description", mode="before")(task_description)
    _due = field_validator("due_date", mode="before")(task_due_date)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set:
            raise ValueError("TASK_UPDATE_REQUIRED")
        return self


class StatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    status: Literal["not_started", "in_progress", "completed"]
    _status = field_validator("status", mode="before")(task_status)


def path_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", value) or int(value) > 9223372036854775807:
        raise ValueError("TASK_ID_INVALID")
    return int(value)


class AssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    team_member_id: str

    @field_validator("team_member_id")
    @classmethod
    def member(cls, value):
        path_id(value)
        return value


class Task(BaseModel):
    id: str
    milestone_id: str
    name: str
    description: str | None
    due_date: date | None
    status: Literal["not_started", "in_progress", "completed"]
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str | None
    completed_at: datetime | None


class User(BaseModel):
    id: str
    full_name: str


class Assignee(BaseModel):
    id: str
    team_member_id: str
    user: User
    assigned_at: datetime


class History(BaseModel):
    id: str
    user: User
    assigned_at: datetime
    unassigned_at: datetime


class TaskResponse(BaseModel):
    data: Task


class Listing(BaseModel):
    milestone: Milestone
    can_manage: bool
    tasks: list[Task]


class ListResponse(BaseModel):
    data: Listing


class AssigneeResponse(BaseModel):
    data: Assignee


class AssigneesResponse(BaseModel):
    data: list[Assignee]


class HistoryResponse(BaseModel):
    data: list[History]


ERRORS = {
    "TASK_NOT_FOUND": (404, "ไม่พบงานที่คุณมีสิทธิ์เข้าถึง"), "MILESTONE_NOT_FOUND": (404, "ไม่พบแผนงานที่คุณมีสิทธิ์เข้าถึง"),
    "ASSIGNEE_NOT_FOUND": (404, "ไม่พบผู้รับผิดชอบรายการนี้"), "TASK_ACTION_FORBIDDEN": (403, "คุณไม่มีสิทธิ์ทำรายการนี้"),
    "TASK_LOCKED": (409, "งานหรือการมอบหมายถูกล็อกในขั้นตอนปัจจุบัน"), "TASK_COMPLETED": (409, "หัวหน้าต้องเปิดงานที่เสร็จแล้วกลับก่อนแก้ไขหรือลบ"),
    "TASK_DUE_DATE_INVALID": (422, "วันกำหนดส่งต้องไม่ก่อนวันนี้ตามเวลาไทยและไม่เกินวันแผนงาน"), "TASK_NAME_CONFLICT": (409, "ชื่องานซ้ำในแผนงานนี้"),
    "TASK_ASSIGNEE_REQUIRED": (409, "ต้องมีผู้รับผิดชอบอย่างน้อยหนึ่งคน"), "TASK_STATUS_CONFLICT": (409, "ไม่สามารถเปลี่ยนสถานะตามที่เลือกได้"),
    "ASSIGNEE_ALREADY_ASSIGNED": (409, "สมาชิกคนนี้เป็นผู้รับผิดชอบงานอยู่แล้ว"), "ASSIGNEE_NOT_CURRENT_MEMBER": (409, "ผู้รับผิดชอบต้องเป็นสมาชิกปัจจุบันของทีมนี้"),
}
router = APIRouter(tags=["tasks"], dependencies=[Depends(require_origin)])


def get_task_uow():
    return task_transaction


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
                raise AuthError(403, "TASK_ACCESS_FORBIDDEN", "หน้านี้สำหรับนักศึกษา")
            result = operation(store, user["id"])
    except MilestoneError as exc:
        code = {"MILESTONE_ACTION_FORBIDDEN": "TASK_ACTION_FORBIDDEN", "MILESTONE_LOCKED": "TASK_LOCKED"}.get(exc.code, "MILESTONE_NOT_FOUND")
        status, message = ERRORS[code]
        raise AuthError(status, code, message) from None
    except TaskError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


def identifier(value):
    try:
        return path_id(value)
    except ValueError:
        raise AuthError(422, "VALIDATION_ERROR", "รหัสงานหรือผู้รับผิดชอบไม่ถูกต้อง") from None


@router.get("/api/v1/milestones/{milestone_id}/tasks", response_model=ListResponse)
def listing(milestone_id: str, request: Request, uow=Depends(get_task_uow)):
    return run(request, uow, lambda s, a: ListResponse(data=s.listing(a, identifier(milestone_id))))


@router.post("/api/v1/milestones/{milestone_id}/tasks", status_code=201, response_model=TaskResponse)
def create(milestone_id: str, payload: CreateInput, request: Request, uow=Depends(get_task_uow)):
    return run(request, uow, lambda s, a: TaskResponse(data=s.create(a, identifier(milestone_id), payload.name, payload.description, payload.due_date)), True)


@router.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
def detail(task_id: str, request: Request, uow=Depends(get_task_uow)):
    return run(request, uow, lambda s, a: TaskResponse(data=s.detail(a, identifier(task_id))))


@router.patch("/api/v1/tasks/{task_id}", response_model=TaskResponse)
def update(task_id: str, payload: UpdateInput, request: Request, uow=Depends(get_task_uow)):
    return run(request, uow, lambda s, a: TaskResponse(data=s.update(a, identifier(task_id), payload.model_dump(exclude_unset=True))), True)


@router.delete("/api/v1/tasks/{task_id}", status_code=204)
def delete(task_id: str, request: Request, uow=Depends(get_task_uow)):
    run(request, uow, lambda s, a: s.delete(a, identifier(task_id)), True)
    return Response(status_code=204)


@router.post("/api/v1/tasks/{task_id}/status", response_model=TaskResponse)
def status(task_id: str, payload: StatusInput, request: Request, uow=Depends(get_task_uow)):
    return run(request, uow, lambda s, a: TaskResponse(data=s.status(a, identifier(task_id), payload.status)), True)


@router.get("/api/v1/tasks/{task_id}/assignees", response_model=AssigneesResponse)
def assignees(task_id: str, request: Request, uow=Depends(get_task_uow)):
    return run(request, uow, lambda s, a: AssigneesResponse(data=s.assignees(a, identifier(task_id))))


@router.post("/api/v1/tasks/{task_id}/assignees", status_code=201, response_model=AssigneeResponse)
def assign(task_id: str, payload: AssignmentInput, request: Request, uow=Depends(get_task_uow)):
    return run(request, uow, lambda s, a: AssigneeResponse(data=s.assign(a, identifier(task_id), identifier(payload.team_member_id))), True)


@router.delete("/api/v1/tasks/{task_id}/assignees/{team_member_id}", status_code=204)
def unassign(task_id: str, team_member_id: str, request: Request, uow=Depends(get_task_uow)):
    run(request, uow, lambda s, a: s.unassign(a, identifier(task_id), identifier(team_member_id)), True)
    return Response(status_code=204)


@router.get("/api/v1/tasks/{task_id}/assignment-history", response_model=HistoryResponse)
def history(task_id: str, request: Request, uow=Depends(get_task_uow)):
    return run(request, uow, lambda s, a: HistoryResponse(data=s.history(a, identifier(task_id))))


async def task_validation_error_handler(request, exc):
    return error_response(422, "VALIDATION_ERROR", "กรุณาตรวจข้อมูลชื่อ คำอธิบาย วันที่ สถานะ หรือผู้รับผิดชอบงาน")


async def task_storage_error_handler(request, exc):
    return error_response(500, "INTERNAL_ERROR", "ระบบงานยังไม่พร้อมใช้งาน กรุณาโหลดข้อมูลอีกครั้ง")
