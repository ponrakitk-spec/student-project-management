"""Student current-team Project create/read/metadata endpoints; no delete API."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from backend.auth_api import (
    ASCII_SPACE, CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, AuthError,
    error_response, require_origin, unauthenticated,
)
from backend.auth_security import session_digest, valid_csrf
from backend.project_store import ProjectError, project_transaction


def database_text(value):
    if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("PROJECT_TEXT_INVALID")
    return value


class ProjectCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_format(cls, value):
        value = database_text(value).strip(ASCII_SPACE)
        if not value:
            raise ValueError("PROJECT_NAME_REQUIRED")
        if len(value) > 255:
            raise ValueError("PROJECT_NAME_TOO_LONG")
        return value

    @field_validator("description")
    @classmethod
    def description_format(cls, value):
        return database_text(value).strip(ASCII_SPACE) or None if value is not None else None


class ProjectUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_format(cls, value):
        if value is None:
            raise ValueError("PROJECT_NAME_REQUIRED")
        return ProjectCreateInput.name_format(value)

    @field_validator("description")
    @classmethod
    def description_format(cls, value):
        return ProjectCreateInput.description_format(value)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("PROJECT_UPDATE_REQUIRED")
        return self


class PublicProject(BaseModel):
    id: str
    name: str
    description: str | None
    team_id: str
    created_by: str


class ProjectResponse(BaseModel):
    data: PublicProject


ERRORS = {
    "TEAM_NOT_FOUND": (404, "คุณยังไม่มีทีม กรุณาสร้างทีมหรือเข้าร่วมทีมก่อน"),
    "PROJECT_NOT_FOUND": (404, "ทีมของคุณยังไม่มีโครงงาน"),
    "PROJECT_CREATION_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมเท่านั้นที่สร้างโครงงานได้"),
    "PROJECT_ALREADY_EXISTS": (409, "ทีมของคุณมีโครงงานแล้ว"),
    "PROJECT_UPDATE_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่แก้ไขโครงงานได้"),
    "PROJECT_METADATA_LOCKED": (409, "ยังแก้ไขข้อมูลโครงงานในขั้นตอนนี้ไม่ได้ กรุณาตรวจสอบผลการส่งโครงงาน"),
}


def get_project_uow():
    return project_transaction


def actor(request, store, *, writing=False):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    user = store.auth.active_user(digest) if digest is not None else None
    if user is None:
        raise unauthenticated()
    if writing and not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
    if user["role"] != "student":
        raise AuthError(403, "PROJECT_ACCESS_FORBIDDEN", "หน้านี้สำหรับโครงงานของทีมนักศึกษาเท่านั้น")
    return user["id"]


router = APIRouter(prefix="/api/v1/projects", tags=["projects"], dependencies=[Depends(require_origin)])


@router.get("/me", response_model=ProjectResponse)
def current_project(request: Request, uow=Depends(get_project_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            result = ProjectResponse(data=store.current(actor(request, store)))
    except ProjectError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


@router.post("", status_code=201, response_model=ProjectResponse)
def create_project(payload: ProjectCreateInput, request: Request, uow=Depends(get_project_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            result = ProjectResponse(data=store.create(payload.name, payload.description, actor(request, store, writing=True)))
    except ProjectError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


@router.patch("/me", response_model=ProjectResponse)
def update_project(payload: ProjectUpdateInput, request: Request, uow=Depends(get_project_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            result = ProjectResponse(data=store.update(
                actor(request, store, writing=True), payload.model_dump(exclude_unset=True)))
    except ProjectError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


async def project_validation_error_handler(request, exc):
    fields = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = location[1] if len(location) > 1 and location[1] in ("name", "description") else "body"
        original = error.get("ctx", {}).get("error")
        code = str(original) if original is not None else ""
        if code not in ("PROJECT_NAME_REQUIRED", "PROJECT_NAME_TOO_LONG", "PROJECT_TEXT_INVALID", "PROJECT_UPDATE_REQUIRED"):
            code = {"missing": "REQUIRED", "extra_forbidden": "UNEXPECTED_FIELD", "json_invalid": "INVALID_JSON"}.get(error["type"], "INVALID_TYPE")
        item = {"field": field, "code": code}
        if item not in fields:
            fields.append(item)
    return error_response(422, "VALIDATION_ERROR", "ข้อมูลโครงงานไม่ถูกต้อง", fields)


async def project_storage_error_handler(request, exc):
    return error_response(500, "INTERNAL_ERROR", "ระบบยังไม่พร้อมใช้งาน กรุณาลองอีกครั้ง")
