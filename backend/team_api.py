"""Session-authenticated create-Team API; request cannot choose the actor."""

from typing import Annotated, Literal
import re

from fastapi import APIRouter, Depends, Request, Response
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.auth_api import (
    ASCII_SPACE, CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, AuthError, LoginInput,
    error_response, require_origin, unauthenticated,
)
from backend.auth_security import session_digest, valid_csrf
from backend.team_store import AlreadyInTeam, TeamMemberError, team_transaction


def require_database_text(value):
    # PostgreSQL UTF-8 text cannot store NUL or unpaired surrogate code points.
    if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("TEAM_TEXT_INVALID")
    return value


class TeamCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_format(cls, value):
        require_database_text(value)
        value = value.strip(ASCII_SPACE)
        if not value:
            raise ValueError("TEAM_NAME_REQUIRED")
        if len(value) > 255:
            raise ValueError("TEAM_NAME_TOO_LONG")
        return value

    @field_validator("description")
    @classmethod
    def description_format(cls, value):
        if value is None:
            return None
        return require_database_text(value).strip(ASCII_SPACE) or None


class TeamUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_format(cls, value):
        if value is None:
            raise ValueError("TEAM_NAME_REQUIRED")
        return TeamCreateInput.name_format(value)

    @field_validator("description")
    @classmethod
    def description_format(cls, value):
        return TeamCreateInput.description_format(value)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("TEAM_UPDATE_REQUIRED")
        return self


class LeaderTransferInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    team_member_id: str

    @field_validator("team_member_id")
    @classmethod
    def member_id_format(cls, value):
        if not re.fullmatch(r"[0-9]{1,19}", value) or not 0 < int(value) <= 9223372036854775807:
            raise ValueError("INVALID_ID")
        return str(int(value))


MembershipId = Annotated[str, AfterValidator(LeaderTransferInput.member_id_format)]


class MembershipExitInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class TeamLeader(BaseModel):
    id: str
    user_id: str
    role: Literal["leader"]


class PublicTeam(BaseModel):
    id: str
    name: str
    description: str | None
    members: list[TeamLeader] = Field(min_length=1, max_length=1)


class TeamCreateResponse(BaseModel):
    data: PublicTeam


class CurrentMembership(BaseModel):
    id: str
    role: Literal["leader", "member"]


class CurrentTeam(BaseModel):
    id: str
    name: str
    description: str | None
    membership: CurrentMembership


class CurrentTeamResponse(BaseModel):
    data: CurrentTeam


class TeamMemberInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    email: str

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        return LoginInput.email_format(require_database_text(value))


class PublicMember(BaseModel):
    id: str
    user_id: str
    full_name: str
    role: Literal["leader", "member"]


class MemberResponse(BaseModel):
    data: PublicMember


class MembersResponse(BaseModel):
    data: list[PublicMember]


MEMBER_ERRORS = {
    "TEAM_NOT_FOUND": (404, "คุณยังไม่มีทีม"),
    "TEAM_MEMBER_ADDITION_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมเท่านั้นที่เพิ่มสมาชิกได้"),
    "MEMBER_NOT_FOUND": (404, "ไม่พบนักศึกษาที่เพิ่มได้ด้วยอีเมลนี้"),
    "MEMBER_UNAVAILABLE": (409, "ไม่สามารถเพิ่มนักศึกษาคนนี้ได้ เนื่องจากมีทีมอยู่แล้ว"),
    "MEMBER_ADDITION_LOCKED": (409, "ช่วงสถานะปัจจุบันยังไม่อนุญาตให้เพิ่มสมาชิก"),
}

UPDATE_ERRORS = {
    "TEAM_NOT_FOUND": MEMBER_ERRORS["TEAM_NOT_FOUND"],
    "TEAM_UPDATE_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่แก้ไขทีมได้"),
    "TEAM_METADATA_LOCKED": (409, "ยังแก้ไขข้อมูลทีมในขั้นตอนนี้ไม่ได้ กรุณาตรวจสอบผลการส่งโครงงาน"),
}

TRANSFER_ERRORS = {
    "TEAM_NOT_FOUND": MEMBER_ERRORS["TEAM_NOT_FOUND"],
    "TEAM_LEADER_TRANSFER_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่โอนหัวหน้าได้"),
    "TEAM_MEMBER_NOT_FOUND": (404, "ไม่พบสมาชิกที่เลือกในทีมของคุณ กรุณาโหลดรายชื่อใหม่"),
    "LEADER_TARGET_INVALID": (409, "กรุณาเลือกสมาชิกคนอื่นในทีมเพื่อรับหน้าที่หัวหน้า"),
}

EXIT_ERRORS = {
    "TEAM_NOT_FOUND": MEMBER_ERRORS["TEAM_NOT_FOUND"],
    "TEAM_MEMBER_NOT_FOUND": TRANSFER_ERRORS["TEAM_MEMBER_NOT_FOUND"],
    "TEAM_MEMBER_REMOVAL_FORBIDDEN": (403, "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่ถอดสมาชิกได้"),
    "TEAM_LEADERSHIP_TRANSFER_REQUIRED": (409, "ต้องโอนตำแหน่งหัวหน้าก่อนออกจากทีมหรือถอดสมาชิกคนนี้"),
    "MEMBER_EXIT_BLOCKED_BY_TASK": (409, "ยังออกหรือถอดสมาชิกไม่ได้ เพราะมีงานที่กำลังทำซึ่งต้องมีผู้รับผิดชอบคนอื่นก่อน"),
}


def member_actor(request, store, *, writing=False):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    user = store.auth.active_user(digest) if digest is not None else None
    if user is None:
        raise unauthenticated()
    if writing and not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
    if user["role"] != "student":
        raise AuthError(403, "TEAM_ACCESS_FORBIDDEN", "หน้านี้สำหรับทีมของนักศึกษาเท่านั้น")
    return user["id"]


def get_team_uow():
    return team_transaction


router = APIRouter(prefix="/api/v1/teams", tags=["teams"], dependencies=[Depends(require_origin)])


@router.get("/me/members", response_model=MembersResponse)
def current_members(request: Request, uow=Depends(get_team_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    with uow() as store:
        members = store.current_members(member_actor(request, store))
        if not members:
            raise AuthError(404, "TEAM_NOT_FOUND", "คุณยังไม่มีทีม")
        result = MembersResponse(data=members)
    return result


@router.post("/me/members", status_code=201, response_model=MemberResponse)
def add_member(payload: TeamMemberInput, request: Request, uow=Depends(get_team_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            actor = member_actor(request, store, writing=True)
            result = MemberResponse(data=store.add_member(actor, payload.email))
    except AlreadyInTeam:
        raise AuthError(409, "MEMBER_UNAVAILABLE", MEMBER_ERRORS["MEMBER_UNAVAILABLE"][1]) from None
    except TeamMemberError as exc:
        status, message = MEMBER_ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


@router.get("/me", response_model=CurrentTeamResponse)
def current_team(request: Request, uow=Depends(get_team_uow)):
    digest = session_digest(request.cookies.get(SESSION_COOKIE))
    if digest is None:
        raise unauthenticated()
    with uow() as store:
        user = store.auth.active_user(digest)
        if user is None:
            raise unauthenticated()
        if user["role"] != "student":
            raise AuthError(403, "TEAM_ACCESS_FORBIDDEN", "หน้านี้สำหรับทีมของนักศึกษาเท่านั้น")
        row = store.current_team(user["id"])
        if row is None:
            raise AuthError(404, "TEAM_NOT_FOUND", "คุณยังไม่มีทีม")
        result = CurrentTeamResponse(data=CurrentTeam(
            id=str(row[0]), name=row[1], description=row[2],
            membership=CurrentMembership(id=str(row[3]), role=row[4])))
    return result


@router.patch("/me", response_model=CurrentTeamResponse)
def update_team(payload: TeamUpdateInput, request: Request, uow=Depends(get_team_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            result = CurrentTeamResponse(data=store.update(
                member_actor(request, store, writing=True), payload.model_dump(exclude_unset=True)))
    except TeamMemberError as exc:
        status, message = UPDATE_ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


@router.post("/me/leader", response_model=CurrentTeamResponse)
def transfer_leader(payload: LeaderTransferInput, request: Request, uow=Depends(get_team_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            result = CurrentTeamResponse(data=store.transfer_leader(
                member_actor(request, store, writing=True), payload.team_member_id))
    except TeamMemberError as exc:
        status, message = TRANSFER_ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return result


@router.post("/me/leave", status_code=204, response_class=Response)
def leave_team(payload: MembershipExitInput, request: Request, uow=Depends(get_team_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            store.exit_member(member_actor(request, store, writing=True))
    except TeamMemberError as exc:
        status, message = EXIT_ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return Response(status_code=204)


@router.post("/me/members/{team_member_id}/remove", status_code=204, response_class=Response)
def remove_member(team_member_id: MembershipId, payload: MembershipExitInput, request: Request, uow=Depends(get_team_uow)):
    if session_digest(request.cookies.get(SESSION_COOKIE)) is None:
        raise unauthenticated()
    try:
        with uow() as store:
            store.exit_member(member_actor(request, store, writing=True), team_member_id)
    except TeamMemberError as exc:
        status, message = EXIT_ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return Response(status_code=204)


@router.post("", status_code=201, response_model=TeamCreateResponse)
def create_team(payload: TeamCreateInput, request: Request, uow=Depends(get_team_uow)):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    if digest is None:
        raise unauthenticated()
    try:
        with uow() as store:
            user = store.auth.active_user(digest)
            if user is None:
                raise unauthenticated()
            if not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
                raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
            if user["role"] != "student":
                raise AuthError(403, "TEAM_CREATION_FORBIDDEN", "เฉพาะนักศึกษาเท่านั้นที่สร้างทีมได้")
            result = TeamCreateResponse(data=PublicTeam(**store.create(
                payload.name, payload.description, user["id"])))
    except AlreadyInTeam:
        raise AuthError(409, "ALREADY_IN_TEAM", "คุณเป็นสมาชิกทีมอยู่แล้ว") from None
    # The transaction must finish successfully before FastAPI gets the result.
    return result


async def team_validation_error_handler(request, exc):
    fields = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = location[1] if len(location) > 1 and location[1] in ("name", "description", "email", "team_member_id") else "body"
        original = error.get("ctx", {}).get("error")
        code = str(original) if original is not None else ""
        if code not in ("TEAM_NAME_REQUIRED", "TEAM_NAME_TOO_LONG", "TEAM_TEXT_INVALID", "TEAM_UPDATE_REQUIRED", "INVALID_ID", "EMAIL_FORMAT_INVALID", "EMAIL_TOO_LONG"):
            code = {"missing": "REQUIRED", "extra_forbidden": "UNEXPECTED_FIELD",
                    "json_invalid": "INVALID_JSON"}.get(error["type"], "INVALID_TYPE")
        item = {"field": field, "code": code}
        if item not in fields:
            fields.append(item)
    return error_response(422, "VALIDATION_ERROR", "ข้อมูลทีมไม่ถูกต้อง", fields)


async def team_storage_error_handler(request, exc):
    return error_response(500, "INTERNAL_ERROR", "ระบบยังไม่พร้อมใช้งาน กรุณาลองอีกครั้ง")
