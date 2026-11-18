"""Opt-in Auth HTTP/ASGI smoke against an approved Supabase test project.

Default is offline. All request connections are borrowed from one outer
force-rollback transaction, authenticated physically as project_app. No owner,
role switch, DDL, grant, persistent fixture or automatic server startup.
"""

import argparse
from contextlib import closing, contextmanager
import hashlib
import json
import re
from threading import RLock
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from backend.auth_api import AuthSettings, CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, get_auth_uow
from backend.auth_security import session_digest, verify_password
from backend.auth_store import AuthRepository, open_auth_connection, runtime_target, transaction_on
from backend.main import create_app
from database.tools.Supabase_Preflight import TABLES, inspect

ORIGIN = "https://spms-cloud-smoke.example.test"
PASSWORD = "CloudSmokeFixtureA1"  # Synthetic test fixture, never a real account.


class SmokeFailed(Exception):
    pass


def require(condition, code):
    if not condition:
        raise SmokeFailed(code)


def validate_target(project_ref):
    require(bool(re.fullmatch(r"[a-z0-9]{20}", project_ref or "")), "PROJECT_REF_REQUIRED")
    target = runtime_target()
    require(target.mode == "supabase_test" and target.database == "postgres", "CLOUD_TEST_PROFILE_REQUIRED")
    host, user = target.connect_kwargs.get("host", ""), target.connect_kwargs.get("user", "")
    direct = host == f"db.{project_ref}.supabase.co" and user == "project_app"
    pooled = host.endswith(".pooler.supabase.com") and user == f"project_app.{project_ref}"
    require(direct or pooled, "EXPLICIT_PROJECT_DOES_NOT_MATCH_CONFIG")
    return target


def fingerprint(conn):
    """Hash visible app rows and metadata; never read protected credentials.

    Credentials existence for this fixture is checked through the reviewed
    lookup function instead. Identity sequence values are intentionally excluded.
    A changed baseline from concurrent writers makes this run fail, not pass.
    """
    require(conn.execute("SHOW transaction_read_only").fetchone() == ("on",), "READONLY_SNAPSHOT_REQUIRED")
    inspect(conn)
    digest = hashlib.sha256()
    tables = [("public", name) for name in TABLES] + [("spms_auth", "sessions")]
    for schema, name in tables:
        query = sql.SQL("SELECT to_jsonb(t) FROM {} t ORDER BY to_jsonb(t)::text").format(sql.Identifier(schema, name))
        digest.update(f"{schema}.{name}".encode())
        for row in conn.execute(query):
            digest.update(json.dumps(row[0], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())
    metadata = conn.execute("""SELECT n.nspname,c.relname,c.relkind,
        pg_get_userbyid(c.relowner),c.relacl::text
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE (n.nspname='public' AND c.relname=ANY(%s))
           OR (n.nspname='spms_auth' AND c.relname IN ('credentials','sessions'))
        ORDER BY 1,2""", (list(TABLES),)).fetchall()
    digest.update(repr(metadata).encode())
    functions = conn.execute("""SELECT n.nspname,p.proname,pg_get_userbyid(p.proowner),
        pg_get_functiondef(p.oid),p.proacl::text
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE (n.nspname='public' AND left(p.proname,3)='v1_') OR n.nspname='spms_auth'
        ORDER BY 1,2,p.oid""").fetchall()
    digest.update(repr(functions).encode())
    return digest.hexdigest()


def snapshot(project_ref, fixture_email=None):
    validate_target(project_ref)
    with closing(open_auth_connection(readonly=True)) as conn:
        try:
            result = fingerprint(conn)
            if fixture_email is not None:
                require(AuthRepository(conn).credentials(fixture_email) is None, "FIXTURE_CREDENTIAL_PERSISTED")
                require(conn.execute("SELECT count(*) FROM public.users WHERE email=%s", (fixture_email,)).fetchone() == (0,), "FIXTURE_USER_PERSISTED")
            return result
        finally:
            conn.rollback()


def sql_diagnostic(exc):
    """Only SQLSTATE and function identifiers, never message/payload/URL."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, psycopg.Error) and exc.sqlstate:
            context = getattr(exc.diag, "context", None) or ""
            return {"sqlstate": exc.sqlstate, "functions": sorted(set(re.findall(r"(?:SQL|PL/pgSQL) function ([a-z_][a-z0-9_.]*)", context)))}
        exc = exc.__context__
    return None


@contextmanager
def borrowed_auth(conn, lock, diagnostics=None):
    with lock:
        require(conn.info.transaction_status == TransactionStatus.INTRANS, "OUTER_ROLLBACK_TRANSACTION_MISSING")
        try:
            with transaction_on(conn) as repository:
                yield repository
        except Exception as exc:
            diagnostic = sql_diagnostic(exc)
            if diagnostic is not None and diagnostics is not None:
                diagnostics.append(diagnostic)
            raise


def exercise(client, conn, email, cases):
    def check(code, condition):
        require(condition, code)
        cases.append(code)
    def post(path, payload=None, headers=None):
        return client.post("/api/v1/auth/" + path, json=payload, headers={"Origin": ORIGIN, **(headers or {})})
    payload = {"full_name": " Cloud Auth Fixture ", "email": email, "password": PASSWORD}
    check("UNAUTHENTICATED_ME_401", client.get("/api/v1/auth/me").status_code == 401)
    check("INVALID_EMAIL_422", post("register", {**payload, "email": "not-an-email"}).status_code == 422)
    check("WEAK_PASSWORD_422", post("register", {**payload, "password": "weak"}).status_code == 422)
    check("ROLE_SPOOF_REJECTED_422", post("register", {**payload, "role": "advisor"}).status_code == 422)
    denied = post("register", payload, {"Origin": "https://other.example.test"})
    check("WRONG_ORIGIN_403", denied.status_code == 403 and not denied.headers.get_list("set-cookie"))
    registered = post("register", {**payload, "email": " " + email.upper() + " "})
    require(registered.status_code == 201, "REGISTER_UNEXPECTED_STATUS")
    user = registered.json()["data"]
    check("REGISTER_STUDENT_201_NORMALIZED", user["email"] == email and user["role"] == "student" and isinstance(user["id"], str) and user["full_name"] == "Cloud Auth Fixture")
    check("REGISTER_NO_AUTOLOGIN", not registered.headers.get_list("set-cookie") and client.get("/api/v1/auth/me").status_code == 401)
    credential = AuthRepository(conn).credentials(email)
    check("ARGON2_HASH_VERIFY", credential is not None and str(credential[0]) == user["id"] and credential[1].startswith("$argon2id$") and verify_password(PASSWORD, credential[1]))
    check("DUPLICATE_EMAIL_409", post("register", payload).status_code == 409 and conn.execute("SELECT count(*) FROM public.users WHERE email=%s", (email,)).fetchone() == (1,))
    wrong = post("login", {"email": email, "password": "WrongCloudFixtureA1"})
    check("WRONG_PASSWORD_401", wrong.status_code == 401 and not wrong.headers.get_list("set-cookie"))
    login = post("login", {"email": email, "password": PASSWORD})
    require(login.status_code == 200, "LOGIN_UNEXPECTED_STATUS")
    headers = login.headers.get_list("set-cookie")
    session_header = next((h for h in headers if h.startswith(SESSION_COOKIE + "=")), "")
    csrf_header = next((h for h in headers if h.startswith(CSRF_COOKIE + "=")), "")
    check("LOGIN_200_SECURE_COOKIES", len(headers) == 2 and all("Secure" in h and "SameSite=lax" in h and "Max-Age=28800" in h and "Domain=" not in h for h in headers) and "HttpOnly" in session_header and "HttpOnly" not in csrf_header and bool(csrf_header))
    token = client.cookies.get(SESSION_COOKIE)
    require(token is not None, "SESSION_COOKIE_MISSING")
    digest = session_digest(token)
    row = conn.execute("SELECT token_hash,extract(epoch FROM expires_at-created_at) FROM spms_auth.sessions WHERE token_hash=%s", (digest,)).fetchone()
    check("SESSION_DIGEST_AND_8H_TTL", row is not None and bytes(row[0]) == digest and len(row[0]) == 32 and abs(float(row[1])-28800) < 2)
    check("ME_200_SESSION_IDENTITY", client.get("/api/v1/auth/me?user_id=999&role=coordinator").json().get("data") == user)
    check("RELOGIN_200", post("login", {"email": email, "password": PASSWORD}).status_code == 200)
    check("RELOGIN_REVOKES_OLD_SESSION", AuthRepository(conn).active_user(digest) is None)
    check("MISSING_CSRF_403", post("logout").status_code == 403)
    check("WRONG_CSRF_403", post("logout", headers={CSRF_HEADER: "0" * 64}).status_code == 403)
    check("REJECTED_LOGOUT_PRESERVES_SESSION", client.get("/api/v1/auth/me").status_code == 200)
    active_token = client.cookies.get(SESSION_COOKIE)
    response = post("logout", headers={CSRF_HEADER: client.cookies.get(CSRF_COOKIE)})
    check("LOGOUT_204_REVOKES_SESSION", response.status_code == 204 and AuthRepository(conn).active_user(session_digest(active_token)) is None)
    check("ME_AFTER_LOGOUT_401", client.get("/api/v1/auth/me").status_code == 401)
    check("FORCED_DEFERRED_CONSTRAINTS", conn.execute("SET CONSTRAINTS ALL IMMEDIATE") is not None)
    return cases


def run(project_ref):
    validate_target(project_ref)
    before = snapshot(project_ref)
    email = "cloud-auth-" + uuid4().hex + "@example.test"
    cases = []
    diagnostics = []
    failure = None
    restored = False
    try:
        validate_target(project_ref)
        with closing(open_auth_connection()) as conn:
            require(conn.pgconn.ssl_in_use, "TLS_REQUIRED")
            # Must be the outermost transaction so no request can commit it.
            require(conn.info.transaction_status == TransactionStatus.IDLE, "IDLE_CONNECTION_REQUIRED")
            with conn.transaction(force_rollback=True):
                from backend.auth_store import assert_auth_connection
                assert_auth_connection(conn)
                app = create_app(AuthSettings.from_environment({"AUTH_WEB_ORIGIN": ORIGIN}))
                lock = RLock()
                app.dependency_overrides[get_auth_uow] = lambda: lambda: borrowed_auth(conn, lock, diagnostics)
                # Any unexpected runtime opener, including other feature stores,
                # fails before creating a connection outside the rollback fixture.
                with patch("psycopg.connect", side_effect=SmokeFailed("UNBORROWED_CONNECTION")):
                    with TestClient(app, base_url=ORIGIN) as client:
                        exercise(client, conn, email, cases)
            require(conn.info.transaction_status == TransactionStatus.IDLE, "ROLLBACK_NOT_COMPLETE")
    except Exception as exc:
        failure = exc
    finally:
        try:
            restored = snapshot(project_ref, email) == before
        except Exception as exc:
            failure = failure or exc
    result = {"result": "PASS" if failure is None and restored else "FAIL", "transport": "HTTP_ASGI",
              "database": "postgres", "role": "project_app", "cases_passed": len(cases),
              "cases": cases, "baseline_restored": restored, "fixture_credentials_absent": restored,
              "rollback_only": True, "identity_sequence_values_excluded": True,
              "browser_proxy_or_vercel_tested": False}
    if failure is not None:
        result["error_type"] = type(failure).__name__
        result["failed_check"] = str(failure) if isinstance(failure, SmokeFailed) else "REDACTED_FAILURE"
        # No raw SQL/driver/HTTP response body/URL/session/password is printed.
        result["sqlstate"] = getattr(failure, "sqlstate", None)
        result["observed_database_errors"] = diagnostics
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--project-ref")
    args = parser.parse_args(argv)
    if not args.run:
        print(json.dumps({"mode": "OFFLINE_PLAN", "execution_requires": "--run --project-ref <approved-ref>", "rollback_only": True}))
        return 0
    try:
        result = run(args.project_ref)
    except Exception as exc:
        result = {"result": "FAIL", "error_type": type(exc).__name__, "reason": "Configuration, connection or baseline check failed; secrets redacted", "sqlstate": getattr(exc, "sqlstate", None)}
    print(json.dumps(result))
    return 0 if result.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
