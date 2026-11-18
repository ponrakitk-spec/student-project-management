"""Session identity for local HTTP or an explicitly selected HTTPS web origin."""

from dataclasses import dataclass
import os
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from backend.auth_security import (
    csrf_token, dummy_password_hash, hash_password, new_session_token,
    session_digest, valid_csrf, verify_password,
)
from backend.auth_store import EmailConflict, StorageUnavailable, auth_transaction
from backend.auth_validation import validate_email_format, validate_new_password

SESSION_COOKIE = "spms_session"
CSRF_COOKIE = "spms_csrf"
CSRF_HEADER = "X-CSRF-Token"
ASCII_SPACE = " \t\n\r\f\v"


@dataclass(frozen=True)
class AuthSettings:
    session_ttl_seconds: int = 8 * 60 * 60
    allowed_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:8000")
    cookie_secure: bool = False  # Local HTTP default; HTTPS profile forces True.

    @classmethod
    def from_environment(cls, values=None):
        values = os.environ if values is None else values
        origin = values.get("AUTH_WEB_ORIGIN") or ""
        if not origin:
            if values.get("VERCEL") == "1":
                raise ValueError("AUTH_WEB_ORIGIN must identify the HTTPS frontend")
            return cls()
        # One canonical web origin: no wildcard previews, client-supplied Host
        # inference, credentials, API paths, query strings or insecure fallback.
        try:
            url = urlsplit(origin)
            if (not origin.isascii() or any(c.isspace() for c in origin)
                or url.scheme != "https" or url.username is not None or url.password is not None
                or url.path not in ("", "/") or url.query or url.fragment
                or url.port not in (None, 443) or not url.hostname
                or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}", url.hostname)):
                raise ValueError()
            canonical = "https://" + url.hostname
        except (TypeError, ValueError):
            raise ValueError("AUTH_WEB_ORIGIN must identify one HTTPS frontend origin") from None
        return cls(allowed_origins=(canonical,), cookie_secure=True)


class AuthError(Exception):
    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    email: str
    password: SecretStr

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        value = value.strip(ASCII_SPACE)
        if len(value) > 255:
            raise ValueError("EMAIL_TOO_LONG")
        return validate_email_format(value)

    @field_validator("password")
    @classmethod
    def nonempty_password(cls, value):
        if not value.get_secret_value():
            raise ValueError("PASSWORD_REQUIRED")
        return value


class RegisterInput(LoginInput):
    full_name: str

    @field_validator("full_name")
    @classmethod
    def name_format(cls, value):
        value = value.strip(ASCII_SPACE)
        if not value:
            raise ValueError("FULL_NAME_REQUIRED")
        if len(value) > 255:
            raise ValueError("FULL_NAME_TOO_LONG")
        return value

    @field_validator("password")
    @classmethod
    def password_policy(cls, value):
        validate_new_password(value.get_secret_value())
        return value


class PublicUser(BaseModel):
    id: str
    full_name: str
    email: str
    role: Literal["student", "advisor", "coordinator"]


class UserResponse(BaseModel):
    data: PublicUser


def get_auth_uow():
    return auth_transaction


def get_auth_settings(request: Request):
    return request.app.state.auth_settings


def require_origin(request: Request, settings: Annotated[AuthSettings, Depends(get_auth_settings)]):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.headers.get("origin") not in settings.allowed_origins:
        raise AuthError(403, "ORIGIN_NOT_ALLOWED", "Origin ไม่ได้รับอนุญาต")


router = APIRouter(prefix="/api/v1/auth", tags=["auth"], dependencies=[Depends(require_origin)])


def public_response(user):
    return UserResponse(data=PublicUser(**user))


def unauthenticated():
    return AuthError(401, "AUTHENTICATION_REQUIRED", "กรุณาเข้าสู่ระบบ")


@router.get("/me", response_model=UserResponse)
def current_user(request: Request, uow=Depends(get_auth_uow)):
    digest = session_digest(request.cookies.get(SESSION_COOKIE))
    if digest is None:
        raise unauthenticated()
    with uow() as store:
        user = store.active_user(digest)
        if user is None:
            raise unauthenticated()
        result = public_response(user)
    # Read only: no session renewal, cookie rotation, or client-supplied identity.
    return result


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterInput, uow=Depends(get_auth_uow)):
    encoded = hash_password(payload.password.get_secret_value())
    with uow() as store:
        result = public_response(store.register(payload.full_name, payload.email, encoded))
    return result


@router.post("/login", response_model=UserResponse)
def login(payload: LoginInput, request: Request, response: Response,
          settings: Annotated[AuthSettings, Depends(get_auth_settings)], uow=Depends(get_auth_uow)):
    with uow() as store:
        credentials = store.credentials(payload.email)
        encoded = credentials[1] if credentials is not None else dummy_password_hash()
        valid = verify_password(payload.password.get_secret_value(), encoded)
        if not valid or credentials is None:
            raise AuthError(401, "INVALID_CREDENTIALS", "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
        user = store.user(credentials[0])
        old_digest = session_digest(request.cookies.get(SESSION_COOKIE))
        if old_digest is not None:
            store.delete_session(old_digest)
        token = new_session_token()
        store.create_session(credentials[0], session_digest(token), settings.session_ttl_seconds)
        result = public_response(user)
    # Never send a successful response/cookie before transaction completion.
    cookie_options = dict(max_age=settings.session_ttl_seconds, path="/",
                          secure=settings.cookie_secure, samesite="lax")
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **cookie_options)
    response.set_cookie(CSRF_COOKIE, csrf_token(token), httponly=False, **cookie_options)
    return result


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request, settings: Annotated[AuthSettings, Depends(get_auth_settings)],
           uow=Depends(get_auth_uow)):
    token = request.cookies.get(SESSION_COOKIE)
    digest = session_digest(token)
    if digest is None:
        raise unauthenticated()
    with uow() as store:
        if store.active_user(digest) is None:
            raise unauthenticated()
        if not valid_csrf(token, request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
            raise AuthError(403, "CSRF_INVALID", "ข้อมูลยืนยันคำขอไม่ถูกต้อง")
        store.delete_session(digest)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.cookie_secure,
                           httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=settings.cookie_secure,
                           httponly=False, samesite="lax")
    return response


def error_response(status, code, message, fields=None):
    error = {"code": code, "message": message}
    if fields is not None:
        error["fields"] = fields
    return JSONResponse(status_code=status, content={"error": error},
                        headers={"Cache-Control": "no-store"})


async def auth_error_handler(request: Request, exc: AuthError):
    return error_response(exc.status, exc.code, exc.message)


async def storage_error_handler(request: Request, exc: StorageUnavailable):
    return error_response(500, "INTERNAL_ERROR", "ระบบยืนยันตัวตนยังไม่พร้อมใช้งาน")


async def conflict_error_handler(request: Request, exc: EmailConflict):
    return error_response(409, "EMAIL_ALREADY_REGISTERED", "อีเมลนี้มีบัญชีอยู่แล้ว")


async def auth_validation_error_handler(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith("/api/v1/auth/"):
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)
    allowed_codes = {
        "EMAIL_TOO_LONG", "EMAIL_FORMAT_INVALID", "PASSWORD_REQUIRED",
        "PASSWORD_TOO_SHORT", "PASSWORD_UPPERCASE_REQUIRED", "PASSWORD_DIGIT_REQUIRED",
        "FULL_NAME_REQUIRED", "FULL_NAME_TOO_LONG",
    }
    fields = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = location[1] if len(location) > 1 else "body"
        if field not in ("email", "password", "full_name"):
            field = "body"
        original = error.get("ctx", {}).get("error")
        code = str(original) if original is not None else ""
        if code not in allowed_codes:
            code = {"missing": "REQUIRED", "extra_forbidden": "UNEXPECTED_FIELD",
                    "json_invalid": "INVALID_JSON"}.get(error["type"], "INVALID_TYPE")
        item = {"field": field, "code": code}
        if item not in fields:
            fields.append(item)
    # Never serialize Pydantic's input/ctx, which can contain a password/body.
    return error_response(422, "VALIDATION_ERROR", "ข้อมูลไม่ถูกต้อง", fields)
