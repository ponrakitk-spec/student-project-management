"""Coordinator roster API: active session, G-12 visibility and existing V1 ACL."""

from typing import Annotated
import re

from fastapi import APIRouter, Depends, Request, Response
from pydantic import AfterValidator, BaseModel, ConfigDict

from backend.auth_api import (
    AuthError, CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, error_response, require_origin, unauthenticated,
)
from backend.auth_security import session_digest, valid_csrf
from backend.committee_store import CommitteeError, committee_transaction

router = APIRouter(prefix="/api/v1/coordinator", tags=["Committee assignments"])


def positive_id(value):
    if not re.fullmatch(r"[1-9][0-9]{0,18}", value) or int(value) > 9223372036854775807:
        raise ValueError("INVALID_ID")
    return value


Identifier = Annotated[str, AfterValidator(positive_id)]


class AssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    advisor_id: Identifier


class RemoveInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


ERRORS = {
    "PROJECT_NOT_FOUND": (404, "ไม่พบโครงงานที่คุณเข้าถึงได้"),
    "COMMITTEE_ASSIGNMENT_NOT_FOUND": (404, "ไม่พบรายการแต่งตั้งกรรมการ"),
    "COMMITTEE_ADVISOR_NOT_FOUND": (404, "ไม่พบอาจารย์ที่แต่งตั้งได้"),
    "COMMITTEE_ROSTER_LOCKED": (409, "รายชื่อกรรมการล็อกแล้วหลังเริ่มลงมติ"),
    "PROJECT_ADVISOR_INELIGIBLE": (409, "อาจารย์ที่ปรึกษาเป็นกรรมการของโครงงานเดียวกันไม่ได้"),
    "COMMITTEE_ADVISOR_ALREADY_ASSIGNED": (409, "อาจารย์ท่านนี้อยู่ในรายชื่อกรรมการแล้ว"),
}


def get_committee_uow():
    return committee_transaction


def actor(request, store):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    user = store.auth.active_user(digest) if digest is not None else None
    if user is None:
        raise unauthenticated()
    if request.method in ("POST", "PATCH") and not valid_csrf(
            token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
    if user["role"] != "coordinator":
        raise AuthError(403, "COMMITTEE_ACCESS_FORBIDDEN", "เฉพาะผู้ประสานงานเท่านั้นที่ใช้หน้านี้ได้")
    return user["id"]


def translate(exc):
    status, message = ERRORS[exc.code]
    raise AuthError(status, exc.code, message) from None


async def committee_validation_error_handler(request, exc):
    return error_response(422, "VALIDATION_ERROR", "กรุณาตรวจสอบข้อมูลกรรมการ")


async def committee_storage_error_handler(request, exc):
    return error_response(500, "INTERNAL_ERROR", "ระบบยังไม่พร้อมใช้งาน กรุณาลองอีกครั้ง")


@router.get("/projects")
def projects(request: Request, uow=Depends(get_committee_uow)):
    with uow() as store:
        result = store.projects(actor(request, store))
    return {"data": result}


@router.get("/projects/{project_id}/committee")
def detail(project_id: Identifier, request: Request, uow=Depends(get_committee_uow)):
    try:
        with uow() as store:
            result = store.detail(actor(request, store), project_id)
    except CommitteeError as exc:
        translate(exc)
    return {"data": result}


@router.get("/projects/{project_id}/committee-candidates")
def candidates(project_id: Identifier, request: Request, uow=Depends(get_committee_uow)):
    try:
        with uow() as store:
            result = store.candidates(actor(request, store), project_id)
    except CommitteeError as exc:
        translate(exc)
    return {"data": result}


def write(request, uow, project, *, operation, advisor=None, assignment=None):
    require_origin(request, request.app.state.auth_settings)
    try:
        with uow() as store:
            result = store.mutate(actor(request, store), project, operation=operation,
                                  advisor=advisor, assignment=assignment)
    except CommitteeError as exc:
        translate(exc)
    return result


@router.post("/projects/{project_id}/committee", status_code=201)
def appoint(project_id: Identifier, payload: AssignmentInput, request: Request, uow=Depends(get_committee_uow)):
    return {"data": write(request, uow, project_id, operation="add", advisor=payload.advisor_id)}


@router.patch("/projects/{project_id}/committee/{assignment_id}")
def replace(project_id: Identifier, assignment_id: Identifier, payload: AssignmentInput,
            request: Request, uow=Depends(get_committee_uow)):
    return {"data": write(request, uow, project_id, operation="replace",
                          advisor=payload.advisor_id, assignment=assignment_id)}


@router.post("/projects/{project_id}/committee/{assignment_id}/remove", status_code=204, response_class=Response)
def remove(project_id: Identifier, assignment_id: Identifier, payload: RemoveInput,
           request: Request, uow=Depends(get_committee_uow)):
    write(request, uow, project_id, operation="remove", assignment=assignment_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
