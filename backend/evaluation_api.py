"""Approved Evaluation endpoints using session identity and V1 SQL guards."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, field_validator

from backend.auth_api import AuthError, CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, error_response, require_origin, unauthenticated
from backend.auth_security import session_digest, valid_csrf
from backend.committee_api import Identifier
from backend.evaluation_store import EvaluationError, evaluation_transaction
from backend.evaluation_validation import validate_comment, validate_score
from backend.topic_vote_store import TopicVoteError

router = APIRouter(prefix="/api/v1", tags=["Evaluations"], dependencies=[Depends(require_origin)])


class EvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    score: int
    comment: str

    @field_validator("score", mode="before")
    @classmethod
    def score_value(cls, value):
        return validate_score(value)

    @field_validator("comment", mode="before")
    @classmethod
    def comment_value(cls, value):
        return validate_comment(value)


ERRORS = {
    "COMMITTEE_PROJECT_NOT_FOUND": (404, "ไม่พบโครงงานที่คุณได้รับแต่งตั้งเป็นกรรมการ"),
    "PROJECT_NOT_FOUND": (404, "ไม่พบโครงงานที่คุณเข้าถึงได้"),
    "TEAM_NOT_FOUND": (404, "ไม่พบทีมปัจจุบันของคุณ"),
    "EVALUATION_ALREADY_RECORDED": (409, "คุณประเมินโครงงานนี้แล้ว ไม่สามารถแก้ไขหรือลบได้"),
    "TOPIC_NOT_APPROVED": (409, "หัวข้อโครงงานยังไม่ผ่านการอนุมัติจากกรรมการ"),
    "COMPLETED_MILESTONE_REQUIRED": (409, "ต้องมี Milestone ที่เสร็จสมบูรณ์อย่างน้อย 1 รายการก่อนประเมิน"),
}


def get_evaluation_uow():
    return evaluation_transaction


def actor(request, store, role, *, committee=False):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    user = store.auth.active_user(digest) if digest is not None else None
    if user is None:
        raise unauthenticated()
    if request.method == "POST" and not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
    if user["role"] != role:
        raise AuthError(403, "EVALUATION_ACCESS_FORBIDDEN" if committee else "EVALUATION_READER_ACCESS_FORBIDDEN",
                        "บทบาทของคุณไม่สามารถใช้หน้านี้ได้")
    return user["id"]


def invoke(request, uow, role, operation, *, committee=False):
    try:
        with uow() as store:
            result = operation(store, actor(request, store, role, committee=committee))
    except (EvaluationError, TopicVoteError) as exc:
        status, message = ERRORS[exc.code]
        raise AuthError(status, exc.code, message) from None
    return {"data": result}


async def evaluation_validation_error_handler(request, exc):
    return error_response(422, "VALIDATION_ERROR", "กรุณาตรวจสอบคะแนนและความคิดเห็น")


async def evaluation_storage_error_handler(request, exc):
    return error_response(500, "INTERNAL_ERROR", "ระบบยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้ง")


@router.get("/committee/projects/{project_id}/evaluations")
def committee_context(project_id: Identifier, request: Request, uow=Depends(get_evaluation_uow)):
    return invoke(request, uow, "advisor", lambda store, user: store.committee_context(user, project_id), committee=True)


@router.post("/committee/projects/{project_id}/evaluations", status_code=201)
def record(project_id: Identifier, payload: EvaluationInput, request: Request, uow=Depends(get_evaluation_uow)):
    return invoke(request, uow, "advisor", lambda store, user: store.record(user, project_id, payload.score, payload.comment), committee=True)


@router.get("/projects/me/evaluations")
def team_context(request: Request, uow=Depends(get_evaluation_uow)):
    return invoke(request, uow, "student", lambda store, user: store.team_context(user))


@router.get("/advisor/projects/{project_id}/evaluations")
def advisor_context(project_id: Identifier, request: Request, uow=Depends(get_evaluation_uow)):
    return invoke(request, uow, "advisor", lambda store, user: store.advisor_context(user, project_id))


@router.get("/coordinator/projects/{project_id}/evaluations")
def coordinator_context(project_id: Identifier, request: Request, uow=Depends(get_evaluation_uow)):
    return invoke(request, uow, "coordinator", lambda store, user: store.coordinator_context(user, project_id))
