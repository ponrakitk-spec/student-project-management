"""Topic vote and result endpoints; role-specific server-side projections."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from backend.auth_api import AuthError, CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, ASCII_SPACE, error_response, require_origin, unauthenticated
from backend.auth_security import session_digest, valid_csrf
from backend.committee_api import Identifier
from backend.team_api import require_database_text
from backend.topic_vote_store import TopicVoteError, topic_vote_transaction

router = APIRouter(prefix="/api/v1", tags=["Topic votes"], dependencies=[Depends(require_origin)])


class VoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    submission_id: Identifier
    vote: Literal["approved", "revision_requested"]
    comment: str | None = None

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value):
        return require_database_text(value).strip(ASCII_SPACE) or None if value is not None else None

    @model_validator(mode="after")
    def revision_requires_comment(self):
        if self.vote == "revision_requested" and self.comment is None:
            raise ValueError("REVISION_COMMENT_REQUIRED")
        return self


ERRORS = {
    "COMMITTEE_PROJECT_NOT_FOUND": (404, "ไม่พบโครงงานที่คุณได้รับแต่งตั้งเป็นกรรมการ"),
    "PROJECT_NOT_FOUND": (404, "ไม่พบโครงงานที่คุณเข้าถึงได้"),
    "TEAM_NOT_FOUND": (404, "ไม่พบทีมปัจจุบันของคุณ"),
    "SUBMISSION_CHANGED": (409, "มีรอบส่งใหม่ กรุณาโหลดหัวข้ออีกครั้งก่อนลงมติ"),
    "SUBMISSION_NOT_APPROVED": (409, "รอบส่งล่าสุดยังไม่ผ่านการอนุมัติจากอาจารย์"),
    "COMMITTEE_INCOMPLETE": (409, "ต้องมีกรรมการอย่างน้อย 3 คนก่อนลงมติ"),
    "VOTE_ALREADY_CAST": (409, "คุณลงมติรอบนี้แล้ว ไม่สามารถลงซ้ำหรือแก้ไขได้"),
}


def get_topic_vote_uow():
    return topic_vote_transaction


def actor(request, store, role, *, committee=False):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    user = store.auth.active_user(digest) if digest is not None else None
    if user is None:
        raise unauthenticated()
    if request.method == "POST" and not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
    if user["role"] != role:
        raise AuthError(403, "VOTE_ACCESS_FORBIDDEN" if committee else "COMMITTEE_READER_ACCESS_FORBIDDEN",
                        "บทบาทของคุณไม่สามารถใช้หน้านี้ได้")
    return user["id"]


def invoke(request, uow, role, operation, *, committee=False):
    try:
        with uow() as store:
            result = operation(store, actor(request, store, role, committee=committee))
    except TopicVoteError as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return {"data": result}


async def topic_vote_validation_error_handler(request, exc):
    return error_response(422, "VALIDATION_ERROR", "กรุณาตรวจสอบข้อมูลการลงมติ")


async def topic_vote_storage_error_handler(request, exc):
    return error_response(500, "INTERNAL_ERROR", "ระบบยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้ง")


@router.get("/committee/projects")
def committee_projects(request: Request, uow=Depends(get_topic_vote_uow)):
    return invoke(request, uow, "advisor", lambda store, user: store.projects(user, "committee"), committee=True)


@router.get("/committee/projects/{project_id}/topic-votes")
def committee_context(project_id: Identifier, request: Request, uow=Depends(get_topic_vote_uow)):
    return invoke(request, uow, "advisor", lambda store, user: store.committee_context(user, project_id), committee=True)


@router.post("/committee/projects/{project_id}/topic-votes", status_code=201)
def cast(project_id: Identifier, payload: VoteInput, request: Request, uow=Depends(get_topic_vote_uow)):
    return invoke(request, uow, "advisor", lambda store, user: store.cast(user, project_id, payload.submission_id,
                  payload.vote, payload.comment), committee=True)


@router.get("/projects/me/committee")
def team_context(request: Request, uow=Depends(get_topic_vote_uow)):
    return invoke(request, uow, "student", lambda store, user: store.team_context(user))


@router.get("/advisor/projects")
def advisor_projects(request: Request, uow=Depends(get_topic_vote_uow)):
    return invoke(request, uow, "advisor", lambda store, user: store.projects(user, "advisor"))


@router.get("/advisor/projects/{project_id}/committee")
def advisor_context(project_id: Identifier, request: Request, uow=Depends(get_topic_vote_uow)):
    return invoke(request, uow, "advisor", lambda store, user: store.advisor_context(user, project_id))


@router.get("/coordinator/projects/{project_id}/topic-votes")
def coordinator_context(project_id: Identifier, request: Request, uow=Depends(get_topic_vote_uow)):
    return invoke(request, uow, "coordinator", lambda store, user: store.coordinator_context(user, project_id))
